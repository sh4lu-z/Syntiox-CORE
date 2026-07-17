---
name: Google Tasks
description: Manage Google Tasks.
---

# Google Tasks Skill (MCP)
**IMPORTANT:** The MCP server path is `D:\\01_PROJECTS\\00_ACTIVE\\J.A.R.V.I.S\\MCP\\google\\tasks_handlers.py`.

## Available Tools:
- `list_task_lists`
- `list_tasks`
- `create_task`
- `update_task`
- `set_task_due_date`
- `complete_task`
- `uncomplete_task`
- `delete_task`
- `move_task_to_list`
- `create_task_list`
- `rename_task_list`
- `delete_task_list`
- `clear_completed_tasks`
- `search_tasks`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    r"D:\\01_PROJECTS\\00_ACTIVE\\J.A.R.V.I.S\\MCP\\google\\tasks_handlers.py",
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
