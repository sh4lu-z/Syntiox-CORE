---
name: Google Slides
description: Manage Google Slides.
---

# Google Slides Skill (MCP)
**IMPORTANT:** The MCP server path is `MCP/google/slides_handlers.py` (relative to the project root).

## Available Tools:
- `list_presentations`
- `get_presentation_info`
- `create_presentation`
- `add_text_slide`
- `get_slides_text`
- `update_slide_text`
- `replace_text_in_presentation`
- `delete_slide`
- `duplicate_slide`
- `reorder_slide`
- `delete_presentation`
- `add_image_slide`
- `add_bullet_slide`
- `update_slide_background`
- `export_presentation`
- `share_presentation`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(os.path.abspath(os.path.join(os.getcwd(), "..")), "MCP", "google", "slides_handlers.py"),
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
