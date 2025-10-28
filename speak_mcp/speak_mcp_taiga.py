"""
Fish TTS MCP Server
Japanese Anime Voice Cloning with Taiga reference
"""
import asyncio
import sys
import time
import base64
from pathlib import Path
from typing import Any
import logging

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Logging configuration
logging.basicConfig(
    filename='mcp_server.log',
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Add console handler (output to stderr)
console = logging.StreamHandler(sys.stderr)
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

# TTS API configuration
TTS_API_URL = "http://localhost:8080/v1/tts"
OUTPUT_DIR = Path("C:/Users/gaterbelt/Downloads/speak_mcp/tts_output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Reference audio configuration
REFERENCE_AUDIO_PATH = Path("C:/Users/gaterbelt/Downloads/speak_mcp/taiga.wav")
REFERENCE_TEXT = "はぁ～ もうヤダヤダ！ 白目むいてたりしてなかった？ もう ほんっと あのときはどうなるかと思った ゴロゴローって転がって 頭打って スーってなって 失神するって あんな感じなんだね 夢の中みたいな感じ"

logging.info(f"=== Fish TTS MCP Server Starting (Taiga Voice Clone) ===")
logging.info(f"Output Directory: {OUTPUT_DIR}")
logging.info(f"TTS API: {TTS_API_URL}")
logging.info(f"Reference Audio: {REFERENCE_AUDIO_PATH}")

# Initialize MCP server
app = Server("fishtts-taiga-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools"""
    logging.debug("list_tools() called")
    
    tools = [
        Tool(
            name="speak_with_tts",
            description="Convert Japanese text to speech using Fish TTS with Taiga voice cloning",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Japanese text to convert to speech (anime style)"
                    }
                },
                "required": ["text"]
            }
        )
    ]
    
    logging.debug(f"Returning {len(tools)} tools")
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Execute tool"""
    logging.info(f"call_tool() - name: {name}, arguments: {arguments}")
    
    if name != "speak_with_tts":
        error_msg = f"Unknown tool: {name}"
        logging.error(error_msg)
        raise ValueError(error_msg)
    
    text = arguments.get("text", "")
    if not text:
        error_msg = "Empty text received"
        logging.error(error_msg)
        return [TextContent(type="text", text="❌ Error: Text is empty")]
    
    try:
        # Check if reference audio exists
        if not REFERENCE_AUDIO_PATH.exists():
            error_msg = f"Reference audio not found: {REFERENCE_AUDIO_PATH}"
            logging.error(error_msg)
            return [TextContent(type="text", text=f"❌ {error_msg}")]
        
        # Read reference audio
        reference_audio_bytes = REFERENCE_AUDIO_PATH.read_bytes()
        reference_audio_base64 = base64.b64encode(reference_audio_bytes).decode('utf-8')
        
        logging.info(f"Reference audio loaded: {len(reference_audio_bytes)} bytes")
        
        # Generate output file path
        timestamp = int(time.time() * 1000)
        output_file = OUTPUT_DIR / f"speech_{timestamp}.wav"
        
        logging.info(f"Processing TTS request - Text: {text}")
        logging.info(f"Output file: {output_file}")
        text = "(screaming)" + text
        # TTS API request with voice cloning
        payload = {
            "text": text,
            "references": [
                {
                    "audio": reference_audio_base64,
                    "text": REFERENCE_TEXT
                }
            ],
            "format": "wav",
            "chunk_length": 200,
            "normalize": True,
            "max_new_tokens": 1024,
            "top_p": 0.8,
            "repetition_penalty": 1.1,
            "temperature": 0.8
        }
        
        logging.debug(f"Sending POST request to {TTS_API_URL}")
        logging.debug(f"Payload keys: {payload.keys()}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                TTS_API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "audio/wav"
                }
            )
            
            logging.info(f"TTS API response status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"TTS API error: {response.status_code} - {response.text}"
                logging.error(error_msg)
                return [TextContent(type="text", text=f"❌ {error_msg}")]
            
            # Save WAV file
            file_size = len(response.content)
            output_file.write_bytes(response.content)
            
            logging.info(f"File saved successfully - Size: {file_size} bytes")
            
            success_msg = f"✅ Speech generated with Taiga voice!\n📁 {output_file.name}\n🎤 Voice: Taiga (Anime Style)\n📝 {text}"
            return [TextContent(type="text", text=success_msg)]
        
    except httpx.TimeoutException as e:
        error_msg = "TTS API timeout (voice cloning may take longer)"
        logging.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=f"⏱️ Error: {error_msg}")]
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=f"❌ Error: {error_msg}")]


async def main():
    """Run MCP server main loop"""
    logging.info("Starting stdio server...")
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            logging.info("Stdio server initialized")
            logging.info("Waiting for client connections...")
            
            init_options = app.create_initialization_options()
            logging.debug(f"Init options: {init_options}")
            
            await app.run(
                read_stream,
                write_stream,
                init_options
            )
            
    except Exception as e:
        logging.error(f"Server error: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)