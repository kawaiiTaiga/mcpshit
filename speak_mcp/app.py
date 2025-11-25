import streamlit as st
import requests
import os
import json
from pathlib import Path
import time

# Configuration
TTS_API_URL = "http://localhost:8088/v1/tts"

# Use absolute path based on script location
SCRIPT_DIR = Path(__file__).parent.resolve()
VOICES_DIR = SCRIPT_DIR / "voices"
VOICES_CONFIG_FILE = SCRIPT_DIR / "voices_config.json"

st.set_page_config(page_title="Fish TTS Manager", layout="wide")

# Ensure directories exist
VOICES_DIR.mkdir(parents=True, exist_ok=True)


def load_voices_config() -> dict:
    """Load voices configuration from JSON file."""
    if VOICES_CONFIG_FILE.exists():
        try:
            with open(VOICES_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Failed to load config: {e}")
    return {"voices": {}}


def save_voices_config(config: dict):
    """Save voices configuration to JSON file."""
    try:
        with open(VOICES_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Failed to save config: {e}")


def get_voices():
    """Return list of voice IDs (based on wav files)."""
    if not VOICES_DIR.exists():
        VOICES_DIR.mkdir(exist_ok=True)
    voices = []
    for f in VOICES_DIR.glob("*.wav"):
        voices.append(f.stem)
    return sorted(voices)


def get_voice_data(voice_id: str) -> dict:
    """Get voice data from config."""
    config = load_voices_config()
    return config.get("voices", {}).get(voice_id, {
        "language": "",
        "reference_text": "",
        "persona": "",
        "expose": False
    })


def save_voice(name: str, file_data, language: str, reference_text: str, persona: str, expose: bool):
    """Save a new voice with all metadata."""
    # Sanitize name
    safe_name = "".join([c for c in name if c.isalpha() or c.isdigit() or c == ' ']).strip().replace(" ", "_")
    filename = f"{safe_name}.wav"
    
    # Save Audio file
    with open(VOICES_DIR / filename, "wb") as f:
        f.write(file_data.getvalue())
    
    # Update config
    config = load_voices_config()
    config["voices"][safe_name] = {
        "language": language,
        "reference_text": reference_text,
        "persona": persona,
        "expose": expose
    }
    save_voices_config(config)
    
    return safe_name


def update_voice_settings(voice_id: str, language: str, reference_text: str, persona: str, expose: bool):
    """Update settings for an existing voice."""
    config = load_voices_config()
    if voice_id not in config.get("voices", {}):
        config["voices"] = config.get("voices", {})
        config["voices"][voice_id] = {}
    
    config["voices"][voice_id] = {
        "language": language,
        "reference_text": reference_text,
        "persona": persona,
        "expose": expose
    }
    save_voices_config(config)


def delete_voice(voice_id: str):
    """Delete a voice and its config."""
    # Delete wav file
    voice_path = VOICES_DIR / f"{voice_id}.wav"
    if voice_path.exists():
        voice_path.unlink()
    
    # Remove from config
    config = load_voices_config()
    if voice_id in config.get("voices", {}):
        del config["voices"][voice_id]
        save_voices_config(config)


def generate_audio(text: str, voice_id: str):
    """Generate and play audio directly in browser."""
    try:
        # 1. Register Reference Voice
        voice_path = VOICES_DIR / f"{voice_id}.wav"
        voice_data = get_voice_data(voice_id)
        
        if voice_path.exists():
            ref_url = TTS_API_URL.replace("/v1/tts", "/v1/references/add")
            
            files = {
                "audio": (voice_path.name, open(voice_path, "rb"), "audio/wav")
            }
            data = {
                "id": voice_id,
                "text": voice_data.get("reference_text", "")
            }
            
            try:
                reg_response = requests.post(ref_url, data=data, files=files, timeout=30)
                if reg_response.status_code not in [200, 201, 409, 422]:
                    st.warning(f"Voice registration warning: {reg_response.status_code}")
            except Exception as e:
                st.error(f"Failed to register voice: {e}")
                return None
        else:
            st.error(f"Voice file {voice_id} not found.")
            return None

        # 2. Generate Speech
        payload = {
            "text": text,
            "chunk_length": 200,
            "format": "wav",
            "mp3_bitrate": 128,
            "normalize": True,
            "opus_bitrate": -1000,
            "reference_id": voice_id
        }
        
        response = requests.post(TTS_API_URL, json=payload, timeout=120)

        if response.status_code != 200:
            st.error(f"TTS Error: {response.status_code} - {response.text}")
            return None
        
        # 3. Return audio data for browser playback
        st.success("✅ Audio generated!")
        return response.content

    except Exception as e:
        st.error(f"Error: {e}")
        return None


# ===== UI =====

# Sidebar
st.sidebar.title("⚙️ Settings")
tts_url = st.sidebar.text_input("TTS API URL", TTS_API_URL)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Status")
config = load_voices_config()
total_voices = len(get_voices())
exposed_voices = sum(1 for v in config.get("voices", {}).values() if v.get("expose", False))
st.sidebar.metric("Total Voices", total_voices)
st.sidebar.metric("Exposed to MCP", exposed_voices)

# Main Content
st.title("🐟 Fish TTS Manager")
st.markdown("Manage voices and control which ones are exposed as MCP tools.")

# Tabs
tab1, tab2, tab3 = st.tabs(["🎤 Add Voice", "📋 Manage Voices", "🔊 Test TTS"])

# ===== Tab 1: Add Voice =====
with tab1:
    st.subheader("Add New Voice")
    
    col1, col2 = st.columns(2)
    
    with col1:
        uploaded_file = st.file_uploader("Upload Reference Audio", type=['wav', 'mp3'])
        new_voice_name = st.text_input("Voice Name (ID)", placeholder="e.g., sakura, john_smith")
        new_voice_lang = st.selectbox("Language", ["ja", "en", "zh", "ko", "es", "fr", "de"])
    
    with col2:
        new_voice_text = st.text_area(
            "Reference Text", 
            placeholder="What is said in the audio file?\nThis helps the TTS model match the voice.",
            height=100
        )
        new_voice_persona = st.text_area(
            "Persona Description",
            placeholder="Describe this voice for the AI assistant.\ne.g., A cheerful young woman who speaks with enthusiasm.",
            height=100
        )
        new_voice_expose = st.checkbox("Expose as MCP Tool", value=True, 
                                        help="If checked, this voice will be available as a tool in MCP clients")
    
    if uploaded_file and st.button("💾 Save Voice", type="primary"):
        if not new_voice_name:
            st.error("Please enter a voice name.")
        elif not new_voice_text:
            st.error("Please enter the reference text.")
        elif not new_voice_persona:
            st.error("Please enter a persona description.")
        else:
            saved_name = save_voice(
                new_voice_name, 
                uploaded_file, 
                new_voice_lang, 
                new_voice_text,
                new_voice_persona,
                new_voice_expose
            )
            st.success(f"✅ Saved voice as '{saved_name}'")
            time.sleep(1)
            st.rerun()

# ===== Tab 2: Manage Voices =====
with tab2:
    st.subheader("Voice Library")
    
    voices = get_voices()
    
    if not voices:
        st.info("No voices found. Add a voice in the 'Add Voice' tab.")
    else:
        # Quick toggle section
        st.markdown("### Quick Expose Toggle")
        st.markdown("Control which voices are exposed as MCP tools:")
        
        config = load_voices_config()
        cols = st.columns(4)
        
        for i, voice_id in enumerate(voices):
            voice_data = get_voice_data(voice_id)
            col = cols[i % 4]
            
            with col:
                current_expose = voice_data.get("expose", False)
                new_expose = st.checkbox(
                    f"🎤 {voice_id}", 
                    value=current_expose,
                    key=f"expose_{voice_id}"
                )
                
                # Auto-save on change
                if new_expose != current_expose:
                    update_voice_settings(
                        voice_id,
                        voice_data.get("language", ""),
                        voice_data.get("reference_text", ""),
                        voice_data.get("persona", ""),
                        new_expose
                    )
                    st.rerun()
        
        st.markdown("---")
        
        # Detailed editor
        st.markdown("### Voice Details Editor")
        selected_voice = st.selectbox("Select Voice to Edit", voices, key="edit_voice_select")
        
        if selected_voice:
            voice_data = get_voice_data(selected_voice)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Voice ID:** `{selected_voice}`")
                st.markdown(f"**Tool Name:** `{selected_voice}_tts`")
                
                edit_lang = st.selectbox(
                    "Language",
                    ["ja", "en", "zh", "ko", "es", "fr", "de"],
                    index=["ja", "en", "zh", "ko", "es", "fr", "de"].index(voice_data.get("language", "en")) 
                        if voice_data.get("language", "en") in ["ja", "en", "zh", "ko", "es", "fr", "de"] else 1,
                    key="edit_language_select"
                )
                
                edit_ref_text = st.text_area(
                    "Reference Text",
                    value=voice_data.get("reference_text", ""),
                    height=100
                )
            
            with col2:
                edit_persona = st.text_area(
                    "Persona Description",
                    value=voice_data.get("persona", ""),
                    height=150,
                    help="This description will appear in the MCP tool description"
                )
                
                edit_expose = st.checkbox(
                    "Expose as MCP Tool",
                    value=voice_data.get("expose", False)
                )
            
            col_save, col_delete = st.columns([3, 1])
            
            with col_save:
                if st.button("💾 Save Changes", type="primary"):
                    update_voice_settings(
                        selected_voice,
                        edit_lang,
                        edit_ref_text,
                        edit_persona,
                        edit_expose
                    )
                    st.success("✅ Voice settings updated!")
                    time.sleep(0.5)
                    st.rerun()
            
            with col_delete:
                if st.button("🗑️ Delete Voice", type="secondary"):
                    delete_voice(selected_voice)
                    st.warning(f"Deleted voice '{selected_voice}'")
                    time.sleep(0.5)
                    st.rerun()

# ===== Tab 3: Test TTS =====
with tab3:
    st.subheader("Test Text-to-Speech")
    
    voices = get_voices()
    
    if not voices:
        st.info("No voices available. Add a voice first.")
    else:
        # Only show exposed voices for testing
        config = load_voices_config()
        exposed_voices = [v for v in voices if config.get("voices", {}).get(v, {}).get("expose", False)]
        
        if not exposed_voices:
            st.warning("No voices are exposed. Enable at least one voice in the 'Manage Voices' tab.")
            test_voice = st.selectbox("Select Voice (including non-exposed)", voices, key="test_voice_all_select")
        else:
            test_voice = st.selectbox("Select Voice", exposed_voices, key="test_voice_select")
        
        if test_voice:
            voice_data = get_voice_data(test_voice)
            
            st.info(f"""
            **Voice:** {test_voice}  
            **Language:** {voice_data.get('language', 'unknown')}  
            **Persona:** {voice_data.get('persona', 'No description')}  
            **Exposed:** {'✅ Yes' if voice_data.get('expose', False) else '❌ No'}
            """)
            
            test_text = st.text_area("Enter text to speak", height=100)
            
            if st.button("🔊 Generate & Play", type="primary"):
                if not test_text:
                    st.warning("Please enter some text.")
                else:
                    with st.spinner("Generating... (This may take 30s+)"):
                        audio_data = generate_audio(test_text, test_voice)
                        if audio_data:
                            st.audio(audio_data, format="audio/wav", autoplay=True)

# Footer
st.markdown("---")
st.markdown("""
**💡 Tips:**
- Each voice with `expose=true` becomes a separate MCP tool (e.g., `sakura_tts`)
- The persona description helps AI assistants understand when to use each voice
- Restart your MCP client after adding/removing exposed voices
""")