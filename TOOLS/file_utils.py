import os
import shutil
import fnmatch
from TOOLS.logger import action_logger

def _resolve_path(path: str) -> str:
    # If the LLM provides an absolute path (e.g., C:\Users\...\Desktop\...), allow it!
    # The user wants the agent to be a powerful assistant that can work anywhere.
    if os.path.isabs(path):
        return os.path.abspath(path)
    else:
        # If it's a relative path (e.g., "script.py"), default to the workspace directory
        # so it doesn't accidentally overwrite its own server source files.
        from backend.config_paths import WORKSPACE_DIR
        workspace = os.path.abspath(WORKSPACE_DIR)
        return os.path.abspath(os.path.join(workspace, path))

def _check_write_permission(path: str) -> None:
    abs_path = os.path.abspath(path).lower()
    # Protect Syntiox CORE system directories in both User Profile and AppData
    appdata = os.environ.get("APPDATA", "").lower()
    userprofile = os.environ.get("USERPROFILE", "").lower()
    
    protected_paths = []
    if appdata:
        protected_paths.append(os.path.join(appdata, ".sh4lu-z").lower())
    if userprofile:
        protected_paths.append(os.path.join(userprofile, ".sh4lu-z").lower())
        
    for protected in protected_paths:
        if abs_path.startswith(protected):
            # Allow modifications ONLY inside the 'workspace' or 'scratch' folders
            workspace_path = os.path.join(protected, "syntiox core", "workspace").lower()
            scratch_path = os.path.join(protected, "syntiox core", "scratch").lower()
            
            if abs_path.startswith(workspace_path) or abs_path.startswith(scratch_path):
                continue
                
            raise PermissionError("Security Policy Violation: You are not allowed to modify Syntiox CORE system files (like history, SKILLS, config). You can only modify files inside the workspace. Ask the user to do it manually.")

@action_logger("view_file")
def view_file(filepath: str, start_line: int = 1, end_line: int = 500) -> str:
    """Reads the contents of a file with line numbers. Use start_line and end_line for pagination."""
    try: filepath = _resolve_path(filepath)
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
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
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
    try: directory = _resolve_path(directory)
    except Exception as e: return str(e)
    
    if not os.path.exists(directory):
        return f"Error: Directory '{directory}' not found."
        
    results = []
    for root, _, files in os.walk(directory):
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
    try: dirpath = _resolve_path(dirpath)
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
    try: directory = _resolve_path(directory)
    except Exception as e: return str(e)
    
    results = []
    if not os.path.exists(directory):
        return f"Error: Directory '{directory}' not found."
        
    for root, _, files in os.walk(directory):
        for file in files:
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

@action_logger("delete_file")
def delete_file(filepath: str) -> str:
    """Deletes a file permanently."""
    try: 
        filepath = _resolve_path(filepath)
        _check_write_permission(filepath)
    except Exception as e: return str(e)
    
    if not os.path.exists(filepath):
        return f"Error: File '{filepath}' does not exist."
    if not os.path.isfile(filepath):
        return f"Error: '{filepath}' is a directory. Use delete_directory."
    try:
        os.remove(filepath)
        return f"Success: Deleted file '{filepath}'"
    except Exception as e:
        return f"Error deleting file: {str(e)}"

@action_logger("delete_directory")
def delete_directory(dirpath: str) -> str:
    """Deletes a directory and all its contents permanently."""
    try: 
        dirpath = _resolve_path(dirpath)
        _check_write_permission(dirpath)
    except Exception as e: return str(e)
    
    if not os.path.exists(dirpath):
        return f"Error: Directory '{dirpath}' does not exist."
    if not os.path.isdir(dirpath):
        return f"Error: '{dirpath}' is a file. Use delete_file."
    try:
        shutil.rmtree(dirpath)
        return f"Success: Deleted directory '{dirpath}'"
    except Exception as e:
        return f"Error deleting directory: {str(e)}"

@action_logger("move_file")
def move_file(src: str, dst: str) -> str:
    """Moves or renames a file or directory from src to dst."""
    try: 
        src = _resolve_path(src)
        dst = _resolve_path(dst)
        _check_write_permission(src)
        _check_write_permission(dst)
    except Exception as e: return str(e)
    
    if not os.path.exists(src):
        return f"Error: Source '{src}' does not exist."
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return f"Success: Moved '{src}' to '{dst}'"
    except Exception as e:
        return f"Error moving file: {str(e)}"

@action_logger("append_to_file")
def append_to_file(filepath: str, content: str) -> str:
    """Appends content to the end of a file."""
    try: 
        filepath = _resolve_path(filepath)
        _check_write_permission(filepath)
    except Exception as e: return str(e)
    
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(content)
        return f"Success: Appended to '{filepath}'"
    except Exception as e:
        return f"Error appending to file: {str(e)}"
