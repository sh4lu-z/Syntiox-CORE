import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_slides_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "slides_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("list_presentations")
def list_presentations(max_results: int = 10) -> str:
    """List Google Slides presentations in Drive."""
    return _run_slides_mcp("list_presentations", {"max_results": max_results})

@action_logger("get_presentation_info")
def get_presentation_info(presentation_id: str) -> str:
    """Get presentation info and slide preview."""
    return _run_slides_mcp("get_presentation_info", {"presentation_id": presentation_id})

@action_logger("create_presentation")
def create_presentation(title: str) -> str:
    """Create a new Google Slides presentation."""
    return _run_slides_mcp("create_presentation", {"title": title})

@action_logger("add_text_slide")
def add_text_slide(presentation_id: str, slide_title: str, slide_body: str) -> str:
    """Add a text slide (title + body) to a presentation."""
    return _run_slides_mcp("add_text_slide", {"presentation_id": presentation_id, "slide_title": slide_title, "slide_body": slide_body})

@action_logger("get_slides_text")
def get_slides_text(presentation_id: str) -> str:
    """Extract all text from a presentation."""
    return _run_slides_mcp("get_slides_text", {"presentation_id": presentation_id})

@action_logger("update_slide_text")
def update_slide_text(presentation_id: str, find_text: str, replace_text: str) -> str:
    """Replace specific text across a presentation."""
    return _run_slides_mcp("update_slide_text", {"presentation_id": presentation_id, "find_text": find_text, "replace_text": replace_text})

@action_logger("replace_text_in_presentation")
def replace_text_in_presentation(presentation_id: str, find_text: str, replace_text: str) -> str:
    """Find and replace text in a presentation."""
    return _run_slides_mcp("replace_text_in_presentation", {"presentation_id": presentation_id, "find_text": find_text, "replace_text": replace_text})

@action_logger("delete_slide")
def delete_slide(presentation_id: str, slide_object_id: str) -> str:
    """Delete a slide by objectId."""
    return _run_slides_mcp("delete_slide", {"presentation_id": presentation_id, "slide_object_id": slide_object_id})

@action_logger("duplicate_slide")
def duplicate_slide(presentation_id: str, slide_object_id: str) -> str:
    """Duplicate a slide."""
    return _run_slides_mcp("duplicate_slide", {"presentation_id": presentation_id, "slide_object_id": slide_object_id})

@action_logger("reorder_slide")
def reorder_slide(presentation_id: str, slide_object_id: str, new_index: int) -> str:
    """Reorder a slide to a new index."""
    return _run_slides_mcp("reorder_slide", {"presentation_id": presentation_id, "slide_object_id": slide_object_id, "new_index": new_index})

@action_logger("delete_presentation")
def delete_presentation(presentation_id: str) -> str:
    """Delete a Google Slides presentation."""
    return _run_slides_mcp("delete_presentation", {"presentation_id": presentation_id})

@action_logger("add_image_slide")
def add_image_slide(presentation_id: str, image_url: str, slide_index: int = None) -> str:
    """Add a blank slide with an image from a URL."""
    return _run_slides_mcp("add_image_slide", {"presentation_id": presentation_id, "image_url": image_url, "slide_index": slide_index})

@action_logger("add_bullet_slide")
def add_bullet_slide(presentation_id: str, title: str, bullets_json: str) -> str:
    """Add a slide with a bulleted list. bullets_json must be a JSON array."""
    return _run_slides_mcp("add_bullet_slide", {"presentation_id": presentation_id, "title": title, "bullets_json": bullets_json})

@action_logger("update_slide_background")
def update_slide_background(presentation_id: str, slide_object_id: str, color_hex: str) -> str:
    """Set the background color of a slide."""
    return _run_slides_mcp("update_slide_background", {"presentation_id": presentation_id, "slide_object_id": slide_object_id, "color_hex": color_hex})

@action_logger("export_presentation")
def export_presentation(presentation_id: str, local_path: str, export_format: str = 'pdf') -> str:
    """Export a presentation to PDF or PPTX."""
    return _run_slides_mcp("export_presentation", {"presentation_id": presentation_id, "local_path": local_path, "export_format": export_format})

@action_logger("share_presentation")
def share_presentation(presentation_id: str, email: str, role: str = 'reader') -> str:
    """Share a presentation via email."""
    return _run_slides_mcp("share_presentation", {"presentation_id": presentation_id, "email": email, "role": role})
