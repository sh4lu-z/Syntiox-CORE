---
name: Google Sheets
description: Manage Google Spreadsheets.
---

# Google Sheets Skill (MCP)
**IMPORTANT:** The MCP server path is `MCP/google/sheets_handlers.py` (relative to the project root).

## Available Tools:
- `list_spreadsheets`
- `create_spreadsheet`
- `read_sheet_data`
- `write_sheet_data`
- `update_single_cell`
- `update_cells_batch`
- `read_sheet_ranges_batch`
- `append_row_to_sheet`
- `get_sheet_names`
- `clear_sheet_range`
- `find_replace_in_sheet`
- `add_sheet_tab`
- `delete_sheet_tab`
- `rename_sheet_tab`
- `duplicate_sheet_tab`
- `format_sheet_cells`
- `auto_resize_columns`
- `sort_sheet_range`
- `copy_spreadsheet`
- `share_spreadsheet`
- `delete_spreadsheet`
- `get_first_empty_row`
- `delete_rows`
- `delete_columns`
- `clear_formatting`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(r"{ROOT_DIR}")
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(r"{ROOT_DIR}", "MCP", "google", "sheets_handlers.py"),
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
