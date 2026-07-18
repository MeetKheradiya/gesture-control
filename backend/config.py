import os
import json
from pathlib import Path

# Base paths
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = WORKSPACE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    # Camera settings
    "camera_index": 0,
    "frame_width": 640,
    "frame_height": 480,
    "flip_camera": True,

    # MediaPipe settings
    "max_num_hands": 1,
    "min_detection_confidence": 0.7,
    "min_tracking_confidence": 0.7,

    # AI Model settings
    "confidence_threshold": 0.85,  # Min confidence to trigger a command
    "cooldown_seconds": 1.5,      # Time to wait between triggering consecutive commands
    
    # TV Driver settings
    "active_driver": "Local",      # Options: 'Local', 'Wi-Fi', 'IR', 'Bluetooth', 'HDMI-CEC'
    "wifi_tv_ip": "192.168.1.100", # Target Smart TV IP
    "wifi_tv_type": "Roku",        # Options: 'Roku', 'AndroidTV'
    "serial_port": "COM3",         # For serial-based IR transmitter
    "serial_baud": 9600,
}

class Config:
    def __init__(self):
        self.settings = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                    self.settings.update(saved)
            except Exception as e:
                print(f"Error loading configuration: {e}. Using defaults.")

    def save(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        if key in self.settings:
            # Cast values to correct type if necessary
            expected_type = type(DEFAULT_SETTINGS[key])
            try:
                if expected_type == int:
                    value = int(value)
                elif expected_type == float:
                    value = float(value)
                elif expected_type == bool:
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes")
                    else:
                        value = bool(value)
            except Exception:
                pass
        self.settings[key] = value
        self.save()

# Global config instance
config = Config()
