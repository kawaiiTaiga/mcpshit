import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "whisper_server_url": "http://localhost:8000",
    "wakeword_models": ["ruby_chan.onnx"],
    "wakeword_threshold": 0.5,
    "max_recording_duration": 10.0,
    "silence_duration": 1.5,
    "silence_threshold": 500,
    "cooldown_time": 3.0,
    "overlay_image_path": "love_live.jpg",
    "overlay_duration_ms": 1500,
    "overlay_sound_file": "wakeword_sound.wav"
}

class ConfigManager:
    def __init__(self, config_file=CONFIG_FILE):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_file):
            return DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            print("Configuration saved.")
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
