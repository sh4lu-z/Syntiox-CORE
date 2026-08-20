# Global state for Syntiox CORE
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", ".env"))

STOP_REQUESTED = False

# Global configuration flags
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local").lower()
VISION_ENABLED = os.getenv("VISION_ENABLED", "false").lower() == "true"
