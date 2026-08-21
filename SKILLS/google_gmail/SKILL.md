---
name: Google Gmail
description: Manage Gmail, send, search, and organize emails.
---

# Google Gmail Skill (MCP)
**IMPORTANT:** The MCP server path is `MCP/google/gmail_handlers.py` (relative to the project root).

## Available Tools:
- `list_latest_emails`
- `send_gmail_email`
- `search_emails`
- `get_email_body`
- `delete_email`
- `mark_email_as_read`
- `reply_to_email`
- `list_email_labels`
- `send_email_with_attachment`
- `mark_email_as_unread`
- `archive_email`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(r"{ROOT_DIR}")
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(r"{ROOT_DIR}", "MCP", "google", "gmail_handlers.py"),
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
