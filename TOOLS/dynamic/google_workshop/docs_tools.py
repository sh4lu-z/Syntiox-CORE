import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_docs_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "docs_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("list_documents")
def list_documents(max_results: int = 10) -> str:
    """List Google Documents in Drive."""
    return _run_docs_mcp("list_documents", {"max_results": max_results})

@action_logger("get_document_content")
def get_document_content(doc_id: str) -> str:
    """Read the text content of a Google Document."""
    return _run_docs_mcp("get_document_content", {"doc_id": doc_id})

@action_logger("get_document_structure")
def get_document_structure(doc_id: str) -> str:
    """List the structure of a Google Document with start and end indices."""
    return _run_docs_mcp("get_document_structure", {"doc_id": doc_id})

@action_logger("create_document")
def create_document(title: str) -> str:
    """Create a new Google Document."""
    return _run_docs_mcp("create_document", {"title": title})

@action_logger("append_text_to_document")
def append_text_to_document(doc_id: str, text: str) -> str:
    """Append text to the end of a Google Document."""
    return _run_docs_mcp("append_text_to_document", {"doc_id": doc_id, "text": text})

@action_logger("insert_text_at_index")
def insert_text_at_index(doc_id: str, index: int, text: str) -> str:
    """Insert text at a specific index in a Google Document."""
    return _run_docs_mcp("insert_text_at_index", {"doc_id": doc_id, "index": index, "text": text})

@action_logger("replace_text_in_document")
def replace_text_in_document(doc_id: str, find_text: str, replace_text: str) -> str:
    """Find and replace all occurrences of text in a Google Document."""
    return _run_docs_mcp("replace_text_in_document", {"doc_id": doc_id, "find_text": find_text, "replace_text": replace_text})

@action_logger("find_replace_in_document")
def find_replace_in_document(doc_id: str, find_text: str, replace_text: str) -> str:
    """Find and replace text (alias)."""
    return _run_docs_mcp("find_replace_in_document", {"doc_id": doc_id, "find_text": find_text, "replace_text": replace_text})

@action_logger("delete_text_range")
def delete_text_range(doc_id: str, start_index: int, end_index: int) -> str:
    """Delete a specific range of text by indices."""
    return _run_docs_mcp("delete_text_range", {"doc_id": doc_id, "start_index": start_index, "end_index": end_index})

@action_logger("add_heading_to_document")
def add_heading_to_document(doc_id: str, text: str, level: int = 1) -> str:
    """Add a heading (level 1 or 2) to the end of a Document."""
    return _run_docs_mcp("add_heading_to_document", {"doc_id": doc_id, "text": text, "level": level})

@action_logger("add_table_to_document")
def add_table_to_document(doc_id: str, rows: int, cols: int) -> str:
    """Add a simple empty table to the end of a Document."""
    return _run_docs_mcp("add_table_to_document", {"doc_id": doc_id, "rows": rows, "cols": cols})

@action_logger("search_documents")
def search_documents(query: str) -> str:
    """Search for Google Documents by name."""
    return _run_docs_mcp("search_documents", {"query": query})

@action_logger("share_document")
def share_document(doc_id: str, email: str, role: str = 'reader') -> str:
    """Share a Google Document via email."""
    return _run_docs_mcp("share_document", {"doc_id": doc_id, "email": email, "role": role})

@action_logger("rename_document")
def rename_document(doc_id: str, new_title: str) -> str:
    """Rename a Google Document."""
    return _run_docs_mcp("rename_document", {"doc_id": doc_id, "new_title": new_title})

@action_logger("delete_document")
def delete_document(doc_id: str, permanent: bool = False) -> str:
    """Delete or trash a Google Document."""
    return _run_docs_mcp("delete_document", {"doc_id": doc_id, "permanent": permanent})

@action_logger("export_document")
def export_document(doc_id: str, local_path: str, export_format: str = 'pdf') -> str:
    """Export a Google Document to a local file (PDF or DOCX)."""
    return _run_docs_mcp("export_document", {"doc_id": doc_id, "local_path": local_path, "export_format": export_format})

@action_logger("read_text_range")
def read_text_range(doc_id: str, start_index: int, end_index: int) -> str:
    """Reads the text content within a specific index range in a Google Document."""
    return _run_docs_mcp("read_text_range", {"doc_id": doc_id, "start_index": start_index, "end_index": end_index})
