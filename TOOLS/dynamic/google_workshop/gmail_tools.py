import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_gmail_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "gmail_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("list_latest_emails")
def list_latest_emails(max_results: int = 5) -> str:
    """List the latest emails in the Inbox."""
    return _run_gmail_mcp("list_latest_emails", {"max_results": max_results})

@action_logger("send_gmail_email")
def send_gmail_email(to_email: str, subject: str, email_body: str) -> str:
    """Send an email via Gmail."""
    return _run_gmail_mcp("send_gmail_email", {"to_email": to_email, "subject": subject, "email_body": email_body})

@action_logger("search_emails")
def search_emails(query: str, max_results: int = 5) -> str:
    """Search for emails in Gmail using queries (e.g. from:x, subject:y)."""
    return _run_gmail_mcp("search_emails", {"query": query, "max_results": max_results})

@action_logger("get_email_body")
def get_email_body(email_id: str) -> str:
    """Get the full content (body) of an email by its ID."""
    return _run_gmail_mcp("get_email_body", {"email_id": email_id})

@action_logger("delete_email")
def delete_email(email_id: str) -> str:
    """Move an email to the Trash."""
    return _run_gmail_mcp("delete_email", {"email_id": email_id})

@action_logger("mark_email_as_read")
def mark_email_as_read(email_id: str) -> str:
    """Mark an email as read."""
    return _run_gmail_mcp("mark_email_as_read", {"email_id": email_id})

@action_logger("reply_to_email")
def reply_to_email(email_id: str, reply_body: str) -> str:
    """Reply to a specific email."""
    return _run_gmail_mcp("reply_to_email", {"email_id": email_id, "reply_body": reply_body})

@action_logger("list_email_labels")
def list_email_labels() -> str:
    """List all Gmail labels/folders."""
    return _run_gmail_mcp("list_email_labels", {})

@action_logger("send_email_with_attachment")
def send_email_with_attachment(to_email: str, subject: str, email_body: str, file_path: str) -> str:
    """Send an email with a file attachment."""
    return _run_gmail_mcp("send_email_with_attachment", {"to_email": to_email, "subject": subject, "email_body": email_body, "file_path": file_path})

@action_logger("mark_email_as_unread")
def mark_email_as_unread(email_id: str) -> str:
    """Mark an email as unread."""
    return _run_gmail_mcp("mark_email_as_unread", {"email_id": email_id})

@action_logger("archive_email")
def archive_email(email_id: str) -> str:
    """Archive an email (removes it from INBOX)."""
    return _run_gmail_mcp("archive_email", {"email_id": email_id})
