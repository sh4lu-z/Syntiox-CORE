---
name: Google Forms
description: Manage Google Forms.
---

# Google Forms Skill (MCP)
**IMPORTANT:** The MCP server path is `MCP/google/forms_handlers.py` (relative to the project root).

## Available Tools:
- `list_forms`
- `create_form`
- `get_form_info`
- `get_form_responses`
- `add_text_question`
- `add_multiple_choice_question`
- `add_checkbox_question`
- `update_form_info`
- `delete_form_question`
- `reorder_form_questions`
- `delete_form`
- `clear_form_responses`
- `get_form_responder_url`
- `duplicate_form`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(r"{ROOT_DIR}")
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(r"{ROOT_DIR}", "MCP", "google", "forms_handlers.py"),
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
