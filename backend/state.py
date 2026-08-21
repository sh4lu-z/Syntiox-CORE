# Global state for Syntiox CORE
import os
from dotenv import load_dotenv
from backend.config_paths import ENV_FILE

load_dotenv(ENV_FILE)

STOP_REQUESTED = False

# Global configuration flags
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local").lower()
VISION_ENABLED = os.getenv("VISION_ENABLED", "false").lower() == "true"
