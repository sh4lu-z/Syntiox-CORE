---
name: Google Drive
description: Manage Drive files/folders.
---

# Google Drive Skill (MCP)
**IMPORTANT:** The MCP server path is `MCP/google/drive_handlers.py` (relative to the project root).

## Available Tools:
- `list_drive_files`
- `search_drive_files`
- `get_drive_file_info`
- `create_drive_folder`
- `delete_drive_file`
- `upload_file_to_drive`
- `download_drive_file`
- `export_google_file`
- `rename_drive_file`
- `move_drive_file`
- `copy_drive_file`
- `share_drive_file`
- `list_file_permissions`
- `trash_drive_file`
- `restore_drive_file`
- `create_drive_shortcut`
- `list_shared_with_me`
- `get_drive_storage_quota`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(os.path.abspath(os.path.join(os.getcwd(), "..")), "MCP", "google", "drive_handlers.py"),
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
