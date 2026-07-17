---
name: Google News
description: Google News RSS.
---

# Google News Skill (MCP)
**IMPORTANT:** The MCP server path is `D:\\01_PROJECTS\\00_ACTIVE\\J.A.R.V.I.S\\MCP\\google\\google_news_handlers.py`.

## Available Tools:
- `get_google_top_news`
- `search_google_news`
- `get_google_news_by_category`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    r"D:\\01_PROJECTS\\00_ACTIVE\\J.A.R.V.I.S\\MCP\\google\\google_news_handlers.py",
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
