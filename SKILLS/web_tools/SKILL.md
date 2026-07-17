---
name: Web Tools
description: Allows the agent to perform web searches and read URL content using MCP.
keywords: search, web, online, internet, find, lookup, url, read, fetch, scrape, who, what, when, where, why, how, news, latest, best
---

# Web Tools Skill (MCP)
You have the ability to search the live internet and read web pages using the `mcp_runner` helper.
When the user asks you to search for something or read a URL, you MUST write a python script to execute it.

**IMPORTANT:** 
1. Use `sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))` (since code runs in the workspace folder) to ensure `backend.mcp_runner` can be imported.
2. The MCP server path is `D:\01_PROJECTS\00_ACTIVE\J.A.R.V.I.S\MCP\web_search_mcp.py`.

## Available Tools:
1. **`search_web`**: Searches the internet. Returns a markdown string with titles, URLs, and descriptions.
   - Argument: `query` (string)

2. **`read_url_content`**: Fetches the content of a specific webpage and converts it to markdown.
   - Argument: `url` (string)

### Code Example for Web Search:
```python
import sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    r"D:\01_PROJECTS\00_ACTIVE\J.A.R.V.I.S\MCP\web_search_mcp.py",
    "search_web",
    {"query": "Latest AI news 2026"}
)
print(result)
```

### Code Example for Reading URL:
```python
import sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    r"D:\01_PROJECTS\00_ACTIVE\J.A.R.V.I.S\MCP\web_search_mcp.py",
    "read_url_content",
    {"url": "https://example.com"}
)
print(result)
```
