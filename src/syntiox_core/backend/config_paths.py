import os
import shutil

PACKAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_DIR = os.path.abspath(os.path.join(PACKAGE_DIR, "..", ".."))
HOME_DIR = os.path.expanduser("~")
DATA_DIR = os.environ.get("SYNTIOX_DATA_DIR", os.path.join(HOME_DIR, ".sh4lu-z", "Syntiox CORE"))

CONFIG_DIR = os.path.join(DATA_DIR, "config")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
WORKSPACE_DIR = os.path.join(DATA_DIR, "workspace")
SKILLS_DIR = os.path.join(DATA_DIR, "skills")
MCP_SCHEMAS_DIR = os.path.join(DATA_DIR, "mcp_schemas")
ENV_FILE = os.path.join(CONFIG_DIR, "local", ".env")
MCP_CONFIG_FILE = os.path.join(CONFIG_DIR, "local", "mcp_servers.json")

# Ensure base directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)
for sub in ("local", "examples", "prompts"):
    os.makedirs(os.path.join(CONFIG_DIR, sub), exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(MCP_SCHEMAS_DIR, exist_ok=True)

# 1 Config files auto-recovery
for cfg_sub in ("local", "examples"):
    cfg_src_dir = os.path.join(BASE_DIR, "config", cfg_sub)
    cfg_dst_dir = os.path.join(CONFIG_DIR, cfg_sub)
    if os.path.exists(cfg_src_dir):
        for item in os.listdir(cfg_src_dir):
            s = os.path.join(cfg_src_dir, item)
            d = os.path.join(cfg_dst_dir, item)
            if os.path.isfile(s) and not os.path.exists(d):
                try: shutil.copy2(s, d)
                except: pass

prompt_src = os.path.join(BASE_DIR, "config", "prompts", "SYNTIOX_CORE.md")
prompt_dst = os.path.join(CONFIG_DIR, "prompts", "SYNTIOX_CORE.md")
if os.path.isfile(prompt_src) and not os.path.exists(prompt_dst):
    try: shutil.copy2(prompt_src, prompt_dst)
    except: pass



if not os.path.exists(ENV_FILE) and os.path.exists(os.path.join(CONFIG_DIR, "examples", ".env.example")):
    try: shutil.copy2(os.path.join(CONFIG_DIR, "examples", ".env.example"), ENV_FILE)
    except: pass

if not os.path.exists(MCP_CONFIG_FILE) and os.path.exists(os.path.join(CONFIG_DIR, "examples", "mcp_servers.json")):
    try: shutil.copy2(os.path.join(CONFIG_DIR, "examples", "mcp_servers.json"), MCP_CONFIG_FILE)
    except: pass

# 2 Skills auto-recovery
if not os.listdir(SKILLS_DIR):
    base_skills = os.path.join(PACKAGE_DIR, "skills")
    if os.path.exists(base_skills):
        try: shutil.copytree(base_skills, SKILLS_DIR, dirs_exist_ok=True)
        except: pass
