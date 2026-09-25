import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_drive_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "drive_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("list_drive_files")
def list_drive_files(max_results: int = 10, folder_name: str = '') -> str:
    """List Google Drive files, optionally within a specific folder."""
    return _run_drive_mcp("list_drive_files", {"max_results": max_results, "folder_name": folder_name})

@action_logger("search_drive_files")
def search_drive_files(query: str, max_results: int = 10) -> str:
    """Search for files in Google Drive by name."""
    return _run_drive_mcp("search_drive_files", {"query": query, "max_results": max_results})

@action_logger("get_drive_file_info")
def get_drive_file_info(file_id: str) -> str:
    """Get detailed information about a Google Drive file."""
    return _run_drive_mcp("get_drive_file_info", {"file_id": file_id})

@action_logger("create_drive_folder")
def create_drive_folder(folder_name: str, parent_folder_id: str = '') -> str:
    """Create a new Google Drive folder."""
    return _run_drive_mcp("create_drive_folder", {"folder_name": folder_name, "parent_folder_id": parent_folder_id})

@action_logger("delete_drive_file")
def delete_drive_file(file_id: str) -> str:
    """Permanently delete a file from Google Drive."""
    return _run_drive_mcp("delete_drive_file", {"file_id": file_id})

@action_logger("upload_file_to_drive")
def upload_file_to_drive(local_file_path: str, drive_folder_id: str = '') -> str:
    """Upload a local file to Google Drive."""
    return _run_drive_mcp("upload_file_to_drive", {"local_file_path": local_file_path, "drive_folder_id": drive_folder_id})

@action_logger("download_drive_file")
def download_drive_file(file_id: str, local_path: str) -> str:
    """Download a Google Drive file to a local path (exports native Google docs to PDF)."""
    return _run_drive_mcp("download_drive_file", {"file_id": file_id, "local_path": local_path})

@action_logger("export_google_file")
def export_google_file(file_id: str, local_path: str, export_format: str = 'pdf') -> str:
    """Export Google Docs/Sheets/Slides to a local file (pdf, docx, xlsx, pptx)."""
    return _run_drive_mcp("export_google_file", {"file_id": file_id, "local_path": local_path, "export_format": export_format})

@action_logger("rename_drive_file")
def rename_drive_file(file_id: str, new_name: str) -> str:
    """Rename a Google Drive file."""
    return _run_drive_mcp("rename_drive_file", {"file_id": file_id, "new_name": new_name})

@action_logger("move_drive_file")
def move_drive_file(file_id: str, new_parent_folder_id: str) -> str:
    """Move a file to a different folder in Google Drive."""
    return _run_drive_mcp("move_drive_file", {"file_id": file_id, "new_parent_folder_id": new_parent_folder_id})

@action_logger("copy_drive_file")
def copy_drive_file(file_id: str, new_name: str = '') -> str:
    """Copy a Google Drive file."""
    return _run_drive_mcp("copy_drive_file", {"file_id": file_id, "new_name": new_name})

@action_logger("share_drive_file")
def share_drive_file(file_id: str, email: str, role: str = 'reader') -> str:
    """Share a Google Drive file with an email address."""
    return _run_drive_mcp("share_drive_file", {"file_id": file_id, "email": email, "role": role})

@action_logger("list_file_permissions")
def list_file_permissions(file_id: str) -> str:
    """List permissions for a Google Drive file."""
    return _run_drive_mcp("list_file_permissions", {"file_id": file_id})

@action_logger("trash_drive_file")
def trash_drive_file(file_id: str) -> str:
    """Move a Google Drive file to the trash."""
    return _run_drive_mcp("trash_drive_file", {"file_id": file_id})

@action_logger("restore_drive_file")
def restore_drive_file(file_id: str) -> str:
    """Restore a trashed Google Drive file."""
    return _run_drive_mcp("restore_drive_file", {"file_id": file_id})

@action_logger("create_drive_shortcut")
def create_drive_shortcut(target_file_id: str, shortcut_name: str, parent_folder_id: str = '') -> str:
    """Create a shortcut to a file in Google Drive."""
    return _run_drive_mcp("create_drive_shortcut", {"target_file_id": target_file_id, "shortcut_name": shortcut_name, "parent_folder_id": parent_folder_id})

@action_logger("list_shared_with_me")
def list_shared_with_me(max_results: int = 10) -> str:
    """List files shared with you in Google Drive."""
    return _run_drive_mcp("list_shared_with_me", {"max_results": max_results})

@action_logger("get_drive_storage_quota")
def get_drive_storage_quota() -> str:
    """Get Google Drive storage quota and usage."""
    return _run_drive_mcp("get_drive_storage_quota", {})
