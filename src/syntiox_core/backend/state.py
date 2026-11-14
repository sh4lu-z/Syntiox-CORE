# Global state for Syntiox CORE
import os
from dotenv import load_dotenv
from backend.config_paths import ENV_FILE, SCRATCH_DIR

if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE)

STOP_REQUESTED = False
STATE_CALLBACK = None
EVENT_CALLBACK = None
WORKSPACE_DIR = None

def get_workspace_dir() -> str:
    if WORKSPACE_DIR and os.path.isdir(WORKSPACE_DIR):
        return WORKSPACE_DIR
    return SCRATCH_DIR

def set_workspace_dir(path: str | None) -> tuple[bool, str]:
    global WORKSPACE_DIR
    if path is None or not str(path).strip() or str(path).strip().lower() == "scratch":
        WORKSPACE_DIR = None
        return True, SCRATCH_DIR

    abs_path = os.path.abspath(os.path.expanduser(str(path).strip().strip('"').strip("'")))
    if not os.path.isdir(abs_path):
        return False, f"Directory not found: {abs_path}"

    WORKSPACE_DIR = abs_path
    return True, WORKSPACE_DIR

def get_workspace_info() -> dict:
    effective = get_workspace_dir()
    return {
        "workspace": WORKSPACE_DIR,
        "effective_dir": effective,
        "scratch_dir": SCRATCH_DIR,
        "is_scratch": WORKSPACE_DIR is None,
    }

def set_ui_state(msg: str):
    from backend import event_bus

    agent_id = event_bus.current_agent()
    if agent_id != "main":
        emit_event({"event": "state", "agent_id": agent_id, "status": msg})
        return
    if STATE_CALLBACK:
        try:
            STATE_CALLBACK(msg)
        except Exception:
            pass

def emit_event(payload: dict):
    if EVENT_CALLBACK:
        try:
            EVENT_CALLBACK(payload)
        except Exception:
            pass
        return
    try:
        from backend import event_bus
        event_bus.publish(payload)
    except Exception:
        pass

# Global configuration flags
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "google").lower()
VISION_ENABLED = os.getenv("VISION_ENABLED", "false").lower() == "true"
