---
name: Google News
description: Google News RSS.
---

# Google News Skill (MCP)
**IMPORTANT:** The MCP server path is `MCP/google/google_news_handlers.py` (relative to the project root).

## Available Tools:
- `get_google_top_news`
- `search_google_news`
- `get_google_news_by_category`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(r"{ROOT_DIR}")
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(r"{ROOT_DIR}", "MCP", "google", "google_news_handlers.py"),
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
