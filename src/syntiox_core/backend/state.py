# Global state for Syntiox CORE
import os
from dotenv import load_dotenv
from backend.config_paths import ENV_FILE

if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE)

STOP_REQUESTED = False
STATE_CALLBACK = None

def set_ui_state(msg: str):
    if STATE_CALLBACK:
        try:
            STATE_CALLBACK(msg)
        except Exception:
            pass

# Global configuration flags
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "google").lower()
VISION_ENABLED = os.getenv("VISION_ENABLED", "false").lower() == "true"
