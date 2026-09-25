import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_tasks_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "tasks_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("list_task_lists")
def list_task_lists() -> str:
    """List all Google Task lists."""
    return _run_tasks_mcp("list_task_lists", {})

@action_logger("list_tasks")
def list_tasks(tasklist_id: str = '@default', show_completed: bool = False) -> str:
    """List tasks within a specific task list."""
    return _run_tasks_mcp("list_tasks", {"tasklist_id": tasklist_id, "show_completed": show_completed})

@action_logger("create_task")
def create_task(title: str, tasklist_id: str = '@default', notes: str = '', due_date: str = '') -> str:
    """Create a new task in a task list."""
    return _run_tasks_mcp("create_task", {"title": title, "tasklist_id": tasklist_id, "notes": notes, "due_date": due_date})

@action_logger("update_task")
def update_task(task_id: str, tasklist_id: str = '@default', title: str = '', notes: str = '', due_date: str = '') -> str:
    """Update a task (title, notes, due date) without completing it."""
    return _run_tasks_mcp("update_task", {"task_id": task_id, "tasklist_id": tasklist_id, "title": title, "notes": notes, "due_date": due_date})

@action_logger("set_task_due_date")
def set_task_due_date(task_id: str, due_date: str, tasklist_id: str = '@default') -> str:
    """Set or change the due date for a task."""
    return _run_tasks_mcp("set_task_due_date", {"task_id": task_id, "due_date": due_date, "tasklist_id": tasklist_id})

@action_logger("complete_task")
def complete_task(task_id: str, tasklist_id: str = '@default') -> str:
    """Mark a task as completed."""
    return _run_tasks_mcp("complete_task", {"task_id": task_id, "tasklist_id": tasklist_id})

@action_logger("uncomplete_task")
def uncomplete_task(task_id: str, tasklist_id: str = '@default') -> str:
    """Reopen a completed task."""
    return _run_tasks_mcp("uncomplete_task", {"task_id": task_id, "tasklist_id": tasklist_id})

@action_logger("delete_task")
def delete_task(task_id: str, tasklist_id: str = '@default') -> str:
    """Delete a task."""
    return _run_tasks_mcp("delete_task", {"task_id": task_id, "tasklist_id": tasklist_id})

@action_logger("move_task_to_list")
def move_task_to_list(task_id: str, source_list_id: str, target_list_id: str) -> str:
    """Move a task from one list to another."""
    return _run_tasks_mcp("move_task_to_list", {"task_id": task_id, "source_list_id": source_list_id, "target_list_id": target_list_id})

@action_logger("create_task_list")
def create_task_list(title: str) -> str:
    """Create a new task list."""
    return _run_tasks_mcp("create_task_list", {"title": title})

@action_logger("rename_task_list")
def rename_task_list(tasklist_id: str, new_title: str) -> str:
    """Rename a task list."""
    return _run_tasks_mcp("rename_task_list", {"tasklist_id": tasklist_id, "new_title": new_title})

@action_logger("delete_task_list")
def delete_task_list(tasklist_id: str) -> str:
    """Delete a task list."""
    return _run_tasks_mcp("delete_task_list", {"tasklist_id": tasklist_id})

@action_logger("clear_completed_tasks")
def clear_completed_tasks(tasklist_id: str = '@default') -> str:
    """Clear all completed tasks from a list."""
    return _run_tasks_mcp("clear_completed_tasks", {"tasklist_id": tasklist_id})

@action_logger("search_tasks")
def search_tasks(query: str, tasklist_id: str = '@default') -> str:
    """Search for tasks by title within a list."""
    return _run_tasks_mcp("search_tasks", {"query": query, "tasklist_id": tasklist_id})
