---
name: Google Docs
description: Manage Google Documents.
---

# Google Docs Skill (MCP)
**IMPORTANT:** The MCP server path is `MCP/google/docs_handlers.py` (relative to the project root).

## Available Tools:
- `create_document(title)`
- `list_documents(max_results)`
- `search_documents(query)`
- `get_document_content(doc_id)`
- `get_document_structure(doc_id)`
- `read_text_range(doc_id, start_index, end_index)`
- `append_text_to_document(doc_id, text)`
- `insert_text_at_index(doc_id, index, text)`
- `delete_text_range(doc_id, start_index, end_index)`
- `replace_text_in_document(doc_id, find_text, replace_text)`
- `add_heading_to_document(doc_id, text, level)`
- `add_table_to_document(doc_id, rows, cols)`
- `rename_document(doc_id, new_title)`
- `share_document(doc_id, email, role)`
- `export_document(doc_id, local_path, export_format)`
- `delete_document(doc_id, permanent)`

### REQUIRED Python Execution Template:
You MUST ALWAYS use this EXACT code structure to call any tool in this skill:
```python
import sys, os
# Add root directory to path to import backend
sys.path.append(r"{ROOT_DIR}")
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(r"{ROOT_DIR}", "MCP", "google", "docs_handlers.py"),
    "TOOL_NAME_HERE",
    {"arg1": "value"}
)
print(result)
```
