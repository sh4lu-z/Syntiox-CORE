import os
import json
import shutil
from datetime import datetime
from colorama import Fore, Style

HISTORY_DIR = "history"
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

def create_new_session_folder(title="Untitled Session"):
    index_data = load_index()
    session_id = get_next_id()
    
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder_name = f"{timestamp_str}_Session_{session_id}"
    session_path = os.path.join(HISTORY_DIR, folder_name)
    os.makedirs(session_path, exist_ok=True)
    
    session_record = {
        "id": session_id,
        "title": title,
        "date": timestamp_str,
        "path": session_path
    }
    index_data.append(session_record)
    save_index(index_data)
    
    return session_id

def save_chat_history(session_id, chat_history):
    if not session_id or not chat_history:
        return
        
    index_data = load_index()
    session_record = next((item for item in index_data if item["id"] == session_id), None)
    
    if session_record:
        session_path = session_record["path"]
        with open(os.path.join(session_path, "chat.json"), "w", encoding="utf-8") as f:
            json.dump(chat_history, f, indent=4, ensure_ascii=False)
            
        # Auto-sync workspace files to history so they are never lost on unexpected exits
        if os.path.exists("workspace/task.md"):
            shutil.copy("workspace/task.md", os.path.join(session_path, "task.md"))
        if os.path.exists("workspace/walkthrough.md"):
            shutil.copy("workspace/walkthrough.md", os.path.join(session_path, "walkthrough.md"))

def archive_workspace_files(session_id):
    if not session_id:
        return
        
    index_data = load_index()
    session_record = next((item for item in index_data if item["id"] == session_id), None)
    
    if session_record:
        session_path = session_record["path"]
        # Archive workspace files if they exist
        if os.path.exists("workspace/task.md"):
            shutil.copy("workspace/task.md", os.path.join(session_path, "task.md"))
        if os.path.exists("workspace/walkthrough.md"):
            shutil.copy("workspace/walkthrough.md", os.path.join(session_path, "walkthrough.md"))

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
    os.makedirs("workspace", exist_ok=True)
    if os.path.exists("workspace/task.md"):
        os.remove("workspace/task.md")
    if os.path.exists("workspace/walkthrough.md"):
        os.remove("workspace/walkthrough.md")
        
    # Restore workspace files
    if os.path.exists(os.path.join(session_path, "task.md")):
        shutil.copy(os.path.join(session_path, "task.md"), "workspace/task.md")
    if os.path.exists(os.path.join(session_path, "walkthrough.md")):
        shutil.copy(os.path.join(session_path, "walkthrough.md"), "workspace/walkthrough.md")
        
    return chat_history, f"Successfully loaded session [{session_id}]: {session_record['title']}"
