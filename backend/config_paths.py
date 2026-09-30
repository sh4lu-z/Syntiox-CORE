import os
import shutil

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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

# 1 Config files auto-recovery
base_config = os.path.join(BASE_DIR, "config")
if os.path.exists(base_config):
    for item in os.listdir(base_config):
        s = os.path.join(base_config, item)
        d = os.path.join(CONFIG_DIR, item)
        if os.path.isfile(s) and not os.path.exists(d):
            try: shutil.copy2(s, d)
            except: pass

if not os.path.exists(ENV_FILE) and os.path.exists(os.path.join(CONFIG_DIR, ".env.example")):
    try: shutil.copy2(os.path.join(CONFIG_DIR, ".env.example"), ENV_FILE)
    except: pass

# 2 Skills auto-recovery
if not os.listdir(SKILLS_DIR):
    base_skills = os.path.join(BASE_DIR, "SKILLS")
    if os.path.exists(base_skills):
        try: shutil.copytree(base_skills, SKILLS_DIR, dirs_exist_ok=True)
        except: pass
