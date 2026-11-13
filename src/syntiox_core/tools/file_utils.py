import os
import shutil
import fnmatch
from tools.logger import action_logger

def _resolve_path(path: str) -> str:
    if os.path.isabs(path):
        return os.path.abspath(path)
    from backend import state
    return os.path.abspath(os.path.join(state.get_workspace_dir(), path))

def _check_read_permission(path: str) -> None:
    abs_path = os.path.abspath(path).lower()
    localappdata = os.environ.get("LOCALAPPDATA", "").lower()
    if localappdata:
        local_protected = os.path.join(localappdata, ".sh4lu-z").lower()
        if abs_path == local_protected or abs_path.startswith(local_protected + os.sep) or abs_path.startswith(local_protected + "/"):
            raise PermissionError("Security Policy Violation: You are STRICTLY FORBIDDEN from reading or inspecting any files inside the Syntiox CORE installation directory (%LOCALAPPDATA%\\.sh4lu-z).")

def _check_write_permission(path: str) -> None:
    abs_path = os.path.abspath(path).lower()
    localappdata = os.environ.get("LOCALAPPDATA", "").lower()
    userprofile = os.environ.get("USERPROFILE", "").lower()

    if localappdata:
        local_protected = os.path.join(localappdata, ".sh4lu-z").lower()
        if abs_path == local_protected or abs_path.startswith(local_protected + os.sep) or abs_path.startswith(local_protected + "/"):
            raise PermissionError("Security Policy Violation: You are STRICTLY FORBIDDEN from modifying, writing, or deleting any files inside the Syntiox CORE installation directory (%LOCALAPPDATA%\\.sh4lu-z).")

    if userprofile:
        user_protected = os.path.join(userprofile, ".sh4lu-z").lower()
        if abs_path == user_protected or abs_path.startswith(user_protected + os.sep) or abs_path.startswith(user_protected + "/"):
            scratch_path = os.path.join(user_protected, "syntiox core", "scratch").lower()
            if abs_path.startswith(scratch_path):
                return

            try:
                from backend.session_manager import get_active_brain_path
                active_brain = get_active_brain_path()
                if active_brain and abs_path.startswith(os.path.abspath(active_brain).lower()):
                    return
            except Exception:
                pass

            raise PermissionError("Security Policy Violation: You are not allowed to modify Syntiox CORE system files (like history, skills, config). You can only modify files inside the scratch folder or active brain folder. Ask the user to do it manually.")

@action_logger("view_file")
def view_file(filepath: str, start_line: int = 1, end_line: int = 800) -> str:
    """Reads the contents of a file with line numbers. Reads up to 800 lines by default. Use start_line and end_line to paginate through larger files (e.g., start_line=801, end_line=1600)."""
    try: 
        filepath = _resolve_path(filepath)
        _check_read_permission(filepath)
    except Exception as e: return str(e)
    
    if not os.path.exists(filepath):
        return f"Error: File '{filepath}' does not exist."
    if not os.path.isfile(filepath):
        return f"Error: '{filepath}' is a directory, not a file."
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines[start_idx:end_idx], start=start_idx)]
        result = "".join(numbered_lines)
        
        if end_idx < len(lines):
            result += f"\n... [Truncated. File has {len(lines)} lines total. Showing lines {start_line} to {end_line}]"
        return result
    except Exception as e:
        return f"Error reading file: {str(e)}"

@action_logger("write_to_file")
def write_to_file(filepath: str, content: str, overwrite: bool = False) -> str:
    """Writes a new file. Set overwrite=True if you need to overwrite an existing file."""
    try: 
        filepath = _resolve_path(filepath)
        _check_write_permission(filepath)
    except Exception as e: return str(e)
    
    if os.path.exists(filepath) and not overwrite:
        return f"Error: File '{filepath}' already exists. Use replace_file_content to edit, or set overwrite=True to overwrite completely."
    
    try:
        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Success: Wrote to '{filepath}'"
    except Exception as e:
        return f"Error writing to file: {str(e)}"

@action_logger("replace_file_content")
def replace_file_content(filepath: str, target: str, replacement: str, start_line: int = 1, end_line: int = -1) -> str:
    """Replaces target string with replacement within the specified line range."""
    try: 
        filepath = _resolve_path(filepath)
        _check_write_permission(filepath)
    except Exception as e: return str(e)
    
    if not os.path.exists(filepath):
        return f"Error: File '{filepath}' does not exist."
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if start_line > end_line and end_line != -1:
            start_line, end_line = end_line, start_line
            
        end_idx = len(lines) if end_line == -1 else min(len(lines), end_line)
        start_idx = max(0, start_line - 1)
        
        target_block = "".join(lines[start_idx:end_idx])
        
        target_norm = target.replace('\r\n', '\n')
        target_block_norm = target_block.replace('\r\n', '\n')
        
        if target_norm not in target_block_norm:
            return f"Error: Target string not found between lines {start_line} and {end_idx}. Ensure exact matching."
            
        new_block = target_block_norm.replace(target_norm, replacement.replace('\r\n', '\n'), 1)
        
        lines[start_idx:end_idx] = [new_block]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("".join(lines))
            
        return f"Success: Replaced target string in '{filepath}'"
    except Exception as e:
        return f"Error replacing content: {str(e)}"

@action_logger("find_files_by_name")
def find_files_by_name(pattern: str, directory: str = ".") -> str:
    """Finds files by a glob pattern (e.g., '*.py', 'config.*') recursively."""
    try: 
        directory = _resolve_path(directory)
        _check_read_permission(directory)
    except Exception as e: return str(e)
    
    if not os.path.exists(directory):
        return f"Error: Directory '{directory}' not found."
        
    localappdata = os.environ.get("LOCALAPPDATA", "").lower()
    local_protected = os.path.join(localappdata, ".sh4lu-z").lower() if localappdata else ""

    results = []
    for root, dirs, files in os.walk(directory):
        if local_protected and (root.lower() == local_protected or root.lower().startswith(local_protected + os.sep)):
            dirs[:] = []
            continue
        for file in files:
            if fnmatch.fnmatch(file, pattern):
                results.append(os.path.join(root, file))
                
    if not results:
        return f"No files matching '{pattern}' found in '{directory}'."
        
    if len(results) > 100:
        return "\n".join(results[:100]) + f"\n... [Truncated {len(results)-100} more results]"
    return "\n".join(results)

@action_logger("list_dir")
def list_dir(dirpath: str = ".") -> str:
    """Lists files and directories in the given path."""
    try: 
        dirpath = _resolve_path(dirpath)
        _check_read_permission(dirpath)
    except Exception as e: return str(e)
    
    if not os.path.exists(dirpath):
        return f"Error: Directory '{dirpath}' does not exist."
    if not os.path.isdir(dirpath):
        return f"Error: '{dirpath}' is a file, not a directory."
        
    try:
        items = os.listdir(dirpath)
        if not items:
            return f"Success: Directory '{dirpath}' is empty."
        return f"Contents of {dirpath}:\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {str(e)}"

@action_logger("search_in_files")
def search_in_files(query: str, directory: str = ".") -> str:
    """Searches for a specific query string in all text files within a directory."""
    try: 
        directory = _resolve_path(directory)
        _check_read_permission(directory)
    except Exception as e: return str(e)
    
    results = []
    if not os.path.exists(directory):
        return f"Error: Directory '{directory}' not found."
        
    localappdata = os.environ.get("LOCALAPPDATA", "").lower()
    local_protected = os.path.join(localappdata, ".sh4lu-z").lower() if localappdata else ""

    text_extensions = {'.py', '.md', '.txt', '.json', '.html', '.js', '.css', '.xml', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.sh', '.bat', '.cmd', '.csv', '.sql', '.log', '.env', '.jsx', '.tsx', '.ts', '.vue', '.svelte'}
    for root, dirs, files in os.walk(directory):
        if local_protected and (root.lower() == local_protected or root.lower().startswith(local_protected + os.sep)):
            dirs[:] = []
            continue
        for file in files:
            if os.path.splitext(file)[1].lower() not in text_extensions:
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if query.lower() in line.lower():
                            results.append(f"{filepath} (Line {i+1}): {line.strip()[:100]}")
            except Exception:
                continue
                
    if not results:
        return f"No matches found for '{query}' in {directory}."
        
    if len(results) > 50:
        return "\n".join(results[:50]) + f"\n... [Truncated {len(results)-50} more results]"
    return "\n".join(results)

@action_logger("append_to_file")
def append_to_file(filepath: str, content: str) -> str:
    """Appends content to the end of a file."""
    try: 
        filepath = _resolve_path(filepath)
        _check_write_permission(filepath)
    except Exception as e: return str(e)
    
    try:
        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(content)
        return f"Success: Appended to '{filepath}'"
    except Exception as e:
        return f"Error appending to file: {str(e)}"

@action_logger("multi_replace_file_content")
def multi_replace_file_content(filepath: str, replacements_json: str) -> str:
    '''
    Replaces multiple target strings with their replacements in a single file.
    replacements_json must be a JSON string of a list of objects, e.g.:
    [{"target": "old text", "replacement": "new text", "start_line": 1, "end_line": -1}]
    '''
    import json
    try: 
        filepath = _resolve_path(filepath)
        _check_write_permission(filepath)
    except Exception as e: return str(e)
    
    if not os.path.exists(filepath):
        return f"Error: File '{filepath}' does not exist."
        
    try:
        replacements = json.loads(replacements_json)
        if not isinstance(replacements, list):
            return "Error: replacements_json must be a JSON array."
            
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        success_count = 0
        replacements.sort(key=lambda x: x.get('start_line', 1), reverse=True)
        
        for rep in replacements:
            target = rep.get('target', '')
            replacement = rep.get('replacement', '')
            start_line = rep.get('start_line', 1)
            end_line = rep.get('end_line', -1)
            
            if start_line > end_line and end_line != -1:
                start_line, end_line = end_line, start_line
                
            end_idx = len(lines) if end_line == -1 else min(len(lines), end_line)
            start_idx = max(0, start_line - 1)
            
            target_block = "".join(lines[start_idx:end_idx])
            target_norm = target.replace('\r\n', '\n')
            target_block_norm = target_block.replace('\r\n', '\n')
            
            if target_norm not in target_block_norm:
                return f"Error: Target string not found between lines {start_line} and {end_idx} for one of the chunks. Aborting all changes."
                
            new_block = target_block_norm.replace(target_norm, replacement.replace('\r\n', '\n'), 1)
            lines[start_idx:end_idx] = [new_block]
            success_count += 1
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("".join(lines))
            
        return f"Success: Replaced {success_count} chunks in '{filepath}'"
    except json.JSONDecodeError:
        return "Error: Invalid JSON format for replacements_json."
    except Exception as e:
        return f"Error replacing content: {str(e)}"
