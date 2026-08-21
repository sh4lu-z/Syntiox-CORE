import os

HOME_DIR = os.path.expanduser("~")
DATA_DIR = os.environ.get("SYNTIOX_DATA_DIR", os.path.join(HOME_DIR, ".sh4lu-z", "Syntiox CORE"))

CONFIG_DIR = os.path.join(DATA_DIR, "config")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
WORKSPACE_DIR = os.path.join(DATA_DIR, "workspace")
SKILLS_DIR = os.path.join(DATA_DIR, "SKILLS")
ENV_FILE = os.path.join(CONFIG_DIR, ".env")

# Ensure they exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(SKILLS_DIR, exist_ok=True)
