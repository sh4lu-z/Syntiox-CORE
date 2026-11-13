import os
import re
from tools.logger import action_logger

@action_logger("grep_search")
def grep_search(query: str, directory: str = ".", is_regex: bool = False, case_insensitive: bool = True) -> str:
    """Searches for text or regex patterns in all files within a directory (similar to ripgrep)."""
    if not os.path.isabs(directory):
        from backend import state
        directory = os.path.abspath(os.path.join(state.get_workspace_dir(), directory))
    if not os.path.exists(directory):
        return f"Error: Directory '{directory}' not found."
        
    results = []
    flags = re.IGNORECASE if case_insensitive else 0
    
    # If it's not a regex, escape it so it's treated as literal text
    search_pattern = query if is_regex else re.escape(query)
    
    try:
        regex = re.compile(search_pattern, flags)
    except re.error as e:
        return f"Error: Invalid regex pattern '{query}': {str(e)}"
        
    text_extensions = {'.py', '.md', '.txt', '.json', '.html', '.js', '.css', '.xml', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.sh', '.bat', '.cmd', '.csv', '.sql', '.log', '.env', '.jsx', '.tsx', '.ts', '.vue', '.svelte'}
    for root, dirs, files in os.walk(directory):
        # Ignore common directories
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', '.chroma_db', 'venv', '.env', '.sh4lu-z']]
        
        for file in files:
            if os.path.splitext(file)[1].lower() not in text_extensions:
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if regex.search(line):
                            results.append(f"{filepath}:{i+1}: {line.strip()[:150]}")
                            if len(results) >= 100:
                                return "\n".join(results) + f"\n... [Truncated. Over 100 matches found.]"
            except Exception:
                continue
                
    if not results:
        return f"No matches found for '{query}' in {directory}."
        
    return "\n".join(results)

if __name__ == "__main__":
    print(grep_search("def ", directory="."))
