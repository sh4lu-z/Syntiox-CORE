import os
import json
import shutil
from datetime import datetime
from colorama import Fore, Style
from backend.config_paths import HISTORY_DIR, WORKSPACE_DIR

INDEX_FILE = os.path.join(HISTORY_DIR, "index.json")

def init_history():
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
    if not os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4)

def load_index():
    init_history()
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_index(index_data):
    init_history()
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=4)

def get_next_id():
    index_data = load_index()
    if not index_data:
        return 1
    return max([item.get("id", 0) for item in index_data]) + 1

ACTIVE_SESSION_PATH = None
ACTIVE_BRAIN_PATH = None

def get_active_session_path():
    global ACTIVE_SESSION_PATH
    return ACTIVE_SESSION_PATH

def set_active_session_path(path):
    global ACTIVE_SESSION_PATH
    ACTIVE_SESSION_PATH = path

def get_active_brain_path():
    global ACTIVE_BRAIN_PATH
    return ACTIVE_BRAIN_PATH

def set_active_brain_path(path):
    global ACTIVE_BRAIN_PATH
    ACTIVE_BRAIN_PATH = path

def create_new_session_folder(title="Untitled Session"):
    index_data = load_index()
    session_id = get_next_id()
    
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{timestamp_str}_Session_{session_id}"
    session_path = os.path.join(HISTORY_DIR, folder_name)
    os.makedirs(session_path, exist_ok=True)
    
    set_active_session_path(session_path)
    
    session_record = {
        "id": session_id,
        "title": title,
        "date": timestamp_str,
        "path": session_path
    }
    index_data.append(session_record)
    save_index(index_data)
    
    return session_id

def create_new_brain_folder(project_name="brain"):
    session_path = get_active_session_path()
    if not session_path:
        # Fallback if no active session (e.g. testing)
        session_path = os.path.join(HISTORY_DIR, "default_session")
        os.makedirs(session_path, exist_ok=True)
        
    brain_base_dir = os.path.join(session_path, "brain")
    os.makedirs(brain_base_dir, exist_ok=True)
    
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Clean project name for folder
    safe_name = "".join([c if c.isalnum() else "_" for c in project_name])
    
    # Check how many brains exist to append index
    existing = len(os.listdir(brain_base_dir)) + 1
    brain_folder_name = f"{timestamp_str}_{safe_name}_{existing}"
    
    brain_path = os.path.join(brain_base_dir, brain_folder_name)
    os.makedirs(brain_path, exist_ok=True)
    set_active_brain_path(brain_path)
    return brain_path

def save_chat_history(session_id, chat_history):
    if not session_id or not chat_history:
        return
        
    index_data = load_index()
    session_record = next((item for item in index_data if item["id"] == session_id), None)
    
    if session_record:
        session_path = session_record["path"]
        with open(os.path.join(session_path, "chat.json"), "w", encoding="utf-8") as f:
            json.dump(chat_history, f, indent=4, ensure_ascii=False)
            
        # Auto-sync: check brain folder first, then workspace fallback
        brain_path = get_active_brain_path()
        sources = []
        if brain_path:
            sources.append(brain_path)
        sources.append(WORKSPACE_DIR)
        
        for src_dir in sources:
            task_md = os.path.join(src_dir, "task.md")
            walk_md = os.path.join(src_dir, "walkthrough.md")
            if os.path.exists(task_md) and not os.path.exists(os.path.join(session_path, "task.md")):
                shutil.copy(task_md, os.path.join(session_path, "task.md"))
            if os.path.exists(walk_md) and not os.path.exists(os.path.join(session_path, "walkthrough.md")):
                shutil.copy(walk_md, os.path.join(session_path, "walkthrough.md"))


def archive_workspace_files(session_id):
    if not session_id:
        return
        
    index_data = load_index()
    session_record = next((item for item in index_data if item["id"] == session_id), None)
    
    if session_record:
        session_path = session_record["path"]
        # Archive from brain folder first, then workspace fallback
        brain_path = get_active_brain_path()
        sources = []
        if brain_path:
            sources.append(brain_path)
        sources.append(WORKSPACE_DIR)
        
        for src_dir in sources:
            task_md = os.path.join(src_dir, "task.md")
            walk_md = os.path.join(src_dir, "walkthrough.md")
            if os.path.exists(task_md) and not os.path.exists(os.path.join(session_path, "task.md")):
                shutil.copy(task_md, os.path.join(session_path, "task.md"))
            if os.path.exists(walk_md) and not os.path.exists(os.path.join(session_path, "walkthrough.md")):
                shutil.copy(walk_md, os.path.join(session_path, "walkthrough.md"))


def list_history():
    index_data = load_index()
    if not index_data:
        return "No chat history found."
        
    # Sort by ID descending (newest first)
    index_data.sort(key=lambda x: x["id"], reverse=True)
    
    output = "📚 **Chat History:**\n\n"
    for item in index_data:
        output += f"**[{item['id']}]** {item['date']} - {item['title']}\n"
    output += "\nType `/load <id>` to restore a session."
    return output

def load_session(session_id_str):
    try:
        session_id = int(session_id_str)
    except:
        return None, "Invalid session ID format."
        
    index_data = load_index()
    session_record = next((item for item in index_data if item["id"] == session_id), None)
    
    if not session_record:
        return None, f"Session ID {session_id} not found."
        
    session_path = session_record["path"]
    if not os.path.exists(session_path):
        return None, f"Session folder missing: {session_path}"
        
    set_active_session_path(session_path)
        
    # Load chat history
    chat_history = []
    chat_file = os.path.join(session_path, "chat.json")
    if os.path.exists(chat_file):
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                chat_history = json.load(f)
        except:
            pass
            
    # Clear current workspace
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    task_md = os.path.join(WORKSPACE_DIR, "task.md")
    walk_md = os.path.join(WORKSPACE_DIR, "walkthrough.md")
    if os.path.exists(task_md):
        os.remove(task_md)
    if os.path.exists(walk_md):
        os.remove(walk_md)
        
    # Restore workspace files
    if os.path.exists(os.path.join(session_path, "task.md")):
        shutil.copy(os.path.join(session_path, "task.md"), task_md)
    if os.path.exists(os.path.join(session_path, "walkthrough.md")):
        shutil.copy(os.path.join(session_path, "walkthrough.md"), walk_md)
        
    return chat_history, f"Successfully loaded session [{session_id}]: {session_record['title']}"
