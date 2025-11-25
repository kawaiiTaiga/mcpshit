"""
Fish TTS MCP Server
Dynamic voice-based TTS tools with persona support
"""
import asyncio
import sys
import json
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

# Configuration
TTS_API_URL = "http://localhost:8088/v1/tts"
AUDIO_PLAYER_URL = "http://localhost:5000/play"

# Use absolute path based on script location
SCRIPT_DIR = Path(__file__).parent.resolve()
VOICES_DIR = SCRIPT_DIR / "voices"
VOICES_CONFIG_FILE = SCRIPT_DIR / "voices_config.json"

# Ensure voices directory exists
VOICES_DIR.mkdir(parents=True, exist_ok=True)

logging.info(f"=== Fish TTS MCP Server Starting ===")
logging.info(f"Voices Directory: {VOICES_DIR.absolute()}")
logging.info(f"Voices Config: {VOICES_CONFIG_FILE.absolute()}")
logging.info(f"TTS API: {TTS_API_URL}")
logging.info(f"Audio Player: {AUDIO_PLAYER_URL}")

# Initialize MCP server
app = Server("SpeakMCP")


def load_voices_config() -> dict:
    """Load voices configuration from JSON file."""
    if VOICES_CONFIG_FILE.exists():
        try:
            with open(VOICES_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load voices config: {e}")
    return {"voices": {}}


def save_voices_config(config: dict):
    """Save voices configuration to JSON file."""
    try:
        with open(VOICES_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to save voices config: {e}")


def get_exposed_voices() -> dict:
    """Get only voices that are marked as exposed."""
    config = load_voices_config()
    voices = config.get("voices", {})
    
    exposed = {}
    for voice_id, voice_data in voices.items():
        # Check if voice file exists and is exposed
        voice_path = VOICES_DIR / f"{voice_id}.wav"
        if voice_path.exists() and voice_data.get("expose", False):
            exposed[voice_id] = voice_data
    
    return exposed


async def send_to_player(audio_data: bytes, player_url: str):
    """
    Send audio to player in background (fire and forget).
    This runs independently and doesn't block the main response.
    """
    try:
        player_files = {
            'audio': ('speech.wav', audio_data, 'audio/wav')
        }
        
        logging.info(f"[Background] Sending {len(audio_data)} bytes to player: {player_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            player_response = await client.post(player_url, files=player_files)
            
            if player_response.status_code == 200:
                logging.info(f"[Background] ✅ Audio sent to player successfully")
            else:
                logging.error(f"[Background] Audio Player error: {player_response.status_code} - {player_response.text}")
                
    except Exception as e:
        logging.error(f"[Background] Failed to send audio to player: {str(e)}", exc_info=True)


async def register_voice(voice_id: str) -> tuple[bool, str]:
    """
    Register a reference voice with the TTS API.
    Returns (success: bool, message: str)
    """
    voice_path = VOICES_DIR / f"{voice_id}.wav"
    
    if not voice_path.exists():
        msg = f"Voice file '{voice_id}.wav' not found in voices directory."
        logging.error(msg)
        return False, msg
    
    # Load voice metadata from config
    config = load_voices_config()
    voice_data = config.get("voices", {}).get(voice_id, {})
    reference_text = voice_data.get("reference_text", "")
    
    ref_url = TTS_API_URL.replace("/v1/tts", "/v1/references/add")
    
    logging.info(f"Registering voice: {voice_id}")
    
    try:
        # Read audio file
        with open(voice_path, "rb") as audio_file:
            audio_data = audio_file.read()
        
        # Prepare multipart form data
        files = {
            "audio": (voice_path.name, audio_data, "audio/wav")
        }
        data = {
            "id": voice_id,
            "text": reference_text
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(ref_url, data=data, files=files)
            
            if response.status_code in [200, 201]:
                msg = f"Voice '{voice_id}' registered successfully."
                logging.info(msg)
                return True, msg
            elif response.status_code == 409:
                msg = f"Voice '{voice_id}' already registered (using existing)."
                logging.info(msg)
                return True, msg
            elif response.status_code == 422:
                msg = f"Voice '{voice_id}' registration warning (proceeding anyway)"
                logging.warning(f"{msg}: {response.text}")
                return True, msg
            else:
                msg = f"Voice registration failed: {response.status_code} - {response.text}"
                logging.error(msg)
                return False, msg
                
    except Exception as e:
        msg = f"Failed to register voice: {str(e)}"
        logging.error(msg, exc_info=True)
        return False, msg


def create_voice_tool_name(voice_id: str) -> str:
    """Create a tool name from voice ID."""
    # Sanitize: replace spaces and special chars with underscore
    safe_name = "".join([c if c.isalnum() else "_" for c in voice_id])
    return f"{safe_name}_tts"


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools - one per exposed voice."""
    logging.debug("list_tools() called")
    
    tools = []
    exposed_voices = get_exposed_voices()
    
    for voice_id, voice_data in exposed_voices.items():
        tool_name = create_voice_tool_name(voice_id)
        persona = voice_data.get("persona", f"Text-to-speech using {voice_id} voice.")
        language = voice_data.get("language", "unknown")
        
        # Build description with persona
        description = f"{persona}\n\nLanguage: {language}"
        
        tool = Tool(
            name=tool_name,
            description=description,
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to speak"
                    }
                },
                "required": ["text"]
            }
        )
        tools.append(tool)
        logging.debug(f"Added tool: {tool_name}")
    
    # If no voices are exposed, add a helper tool
    if not tools:
        tools.append(Tool(
            name="no_voices_available",
            description="No TTS voices are currently available. Please add and expose voices using the Fish TTS Manager app.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ))
    
    logging.info(f"Returning {len(tools)} tools: {[t.name for t in tools]}")
    return tools


def extract_voice_id_from_tool_name(tool_name: str) -> str | None:
    """Extract voice_id from tool name (reverse of create_voice_tool_name)."""
    if not tool_name.endswith("_tts"):
        return None
    
    # Find matching voice in config
    config = load_voices_config()
    voices = config.get("voices", {})
    
    for voice_id in voices.keys():
        if create_voice_tool_name(voice_id) == tool_name:
            return voice_id
    
    return None


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Execute tool"""
    logging.info(f"call_tool() - name: {name}, arguments: {arguments}")
    
    try:
        # Handle placeholder tool
        if name == "no_voices_available":
            return [TextContent(
                type="text", 
                text="⚠️ No TTS voices are available. Please use the Fish TTS Manager (app.py) to add voices and enable them."
            )]
        
        # Extract voice_id from tool name
        voice_id = extract_voice_id_from_tool_name(name)
        
        if voice_id:
            return await handle_speak(voice_id, arguments)
        else:
            error_msg = f"Unknown tool: {name}"
            logging.error(error_msg)
            return [TextContent(type="text", text=f"❌ Error: {error_msg}")]
            
    except Exception as e:
        error_msg = f"Tool execution error: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=f"❌ Error: {error_msg}")]


async def handle_speak(voice_id: str, arguments: dict) -> list[TextContent]:
    """Handle TTS for a specific voice."""
    text = arguments.get("text", "")
    
    if not text:
        return [TextContent(type="text", text="❌ Error: Text is empty")]
    
    logging.info(f"Speaking text: '{text[:50]}...' with voice_id={voice_id}")
    
    try:
        # Step 1: Register voice
        success, msg = await register_voice(voice_id)
        if not success:
            return [TextContent(type="text", text=f"❌ Error: {msg}")]
        logging.info(f"Voice registration: {msg}")
        
        # Step 2: Generate speech
        payload = {
            "text": text,
            "chunk_length": 200,
            "format": "wav",
            "mp3_bitrate": 128,
            "normalize": True,
            "opus_bitrate": -1000,
            "reference_id": voice_id
        }
        
        logging.info(f"Sending TTS request to {TTS_API_URL}")
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            tts_response = await client.post(TTS_API_URL, json=payload)
            
            if tts_response.status_code != 200:
                error_msg = f"TTS API error: {tts_response.status_code} - {tts_response.text}"
                logging.error(error_msg)
                return [TextContent(type="text", text=f"❌ {error_msg}")]
            
            audio_data = tts_response.content
            logging.info(f"TTS generated successfully: {len(audio_data)} bytes")
        
        # Step 3: Send to audio player (fire and forget)
        success_msg = f"✅ Audio generated with voice '{voice_id}' and sending to player...\n📝 Text: {text[:100]}{'...' if len(text) > 100 else ''}\n🔊 Audio will play automatically."
        
        asyncio.create_task(send_to_player(audio_data, AUDIO_PLAYER_URL))
        
        logging.info(success_msg)
        return [TextContent(type="text", text=success_msg)]
    
    except httpx.TimeoutException:
        error_msg = "Request timed out. TTS generation or audio player not responding."
        logging.error(error_msg)
        return [TextContent(type="text", text=f"⏱️ Error: {error_msg}")]
    
    except httpx.ConnectError as e:
        error_msg = f"Cannot connect to TTS API or Audio Player. Are they running? ({str(e)})"
        logging.error(error_msg)
        return [TextContent(type="text", text=f"🔌 Error: {error_msg}")]
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=f"❌ Error: {error_msg}")]


async def main():
    """Run MCP server main loop"""
    logging.info("Starting stdio server...")
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            logging.info("✅ Stdio server initialized")
            logging.info("📡 Waiting for client connections...")
            
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