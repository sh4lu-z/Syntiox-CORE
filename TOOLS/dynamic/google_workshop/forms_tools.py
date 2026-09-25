import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_forms_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "forms_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("list_forms")
def list_forms(max_results: int = 10) -> str:
    """List Google Forms in Drive."""
    return _run_forms_mcp("list_forms", {"max_results": max_results})

@action_logger("create_form")
def create_form(title: str, description: str = '') -> str:
    """Create a new Google Form."""
    return _run_forms_mcp("create_form", {"title": title, "description": description})

@action_logger("get_form_info")
def get_form_info(form_id: str) -> str:
    """Get Form details and questions."""
    return _run_forms_mcp("get_form_info", {"form_id": form_id})

@action_logger("get_form_responses")
def get_form_responses(form_id: str, max_responses: int = 10) -> str:
    """Get Form responses."""
    return _run_forms_mcp("get_form_responses", {"form_id": form_id, "max_responses": max_responses})

@action_logger("add_text_question")
def add_text_question(form_id: str, question_title: str, required: bool = False) -> str:
    """Add a text question to a Form."""
    return _run_forms_mcp("add_text_question", {"form_id": form_id, "question_title": question_title, "required": required})

@action_logger("add_multiple_choice_question")
def add_multiple_choice_question(form_id: str, question_title: str, options_json: str, required: bool = False) -> str:
    """Add a multiple choice question to a Form. options_json must be a JSON array."""
    return _run_forms_mcp("add_multiple_choice_question", {"form_id": form_id, "question_title": question_title, "options_json": options_json, "required": required})

@action_logger("add_checkbox_question")
def add_checkbox_question(form_id: str, question_title: str, options_json: str, required: bool = False) -> str:
    """Add a checkbox question to a Form. options_json must be a JSON array."""
    return _run_forms_mcp("add_checkbox_question", {"form_id": form_id, "question_title": question_title, "options_json": options_json, "required": required})

@action_logger("update_form_info")
def update_form_info(form_id: str, title: str = '', description: str = '') -> str:
    """Update Form title or description."""
    return _run_forms_mcp("update_form_info", {"form_id": form_id, "title": title, "description": description})

@action_logger("delete_form_question")
def delete_form_question(form_id: str, item_id: str) -> str:
    """Delete a question from a Form."""
    return _run_forms_mcp("delete_form_question", {"form_id": form_id, "item_id": item_id})

@action_logger("reorder_form_questions")
def reorder_form_questions(form_id: str, item_id: str, new_index: int) -> str:
    """Reorder a question in a Form."""
    return _run_forms_mcp("reorder_form_questions", {"form_id": form_id, "item_id": item_id, "new_index": new_index})

@action_logger("delete_form")
def delete_form(form_id: str) -> str:
    """Delete a Google Form."""
    return _run_forms_mcp("delete_form", {"form_id": form_id})

@action_logger("clear_form_responses")
def clear_form_responses(form_id: str) -> str:
    """Clear all responses for a Form."""
    return _run_forms_mcp("clear_form_responses", {"form_id": form_id})

@action_logger("get_form_responder_url")
def get_form_responder_url(form_id: str) -> str:
    """Get the public responder URL for a Form."""
    return _run_forms_mcp("get_form_responder_url", {"form_id": form_id})

@action_logger("duplicate_form")
def duplicate_form(form_id: str, new_title: str) -> str:
    """Duplicate a Google Form."""
    return _run_forms_mcp("duplicate_form", {"form_id": form_id, "new_title": new_title})
