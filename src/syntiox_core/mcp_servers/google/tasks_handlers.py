"""
🎯 Google Tasks Handler Tools
"""
from mcp.server.fastmcp import FastMCP
from google_common import get_service

mcp = FastMCP("Google-Tasks-Tools")


def _tasks():
    return get_service('tasks', 'v1')


@mcp.tool()
def list_task_lists() -> str:
    """List all Google Task lists."""
    try:
        lists = _tasks().tasklists().list(maxResults=20).execute().get('items', [])
        if not lists:
            return "📋 No task lists found."
        output = f"📋 TASK LISTS — {len(lists)}\n{'─'*35}\n"
        for tl in lists:
            output += f"  📌 {tl['title']} (ID: {tl['id']})\n"
        return output
    except Exception as e:
        return f"❌ Error listing task lists: {e}"


@mcp.tool()
def list_tasks(tasklist_id: str = "@default", show_completed: bool = False) -> str:
    """List tasks within a specific task list."""
    try:
        tasks = _tasks().tasks().list(
            tasklist=tasklist_id, showCompleted=show_completed, maxResults=50
        ).execute().get('items', [])
        if not tasks:
            return "✅ No tasks found."
        pending = [t for t in tasks if t.get('status') != 'completed']
        completed = [t for t in tasks if t.get('status') == 'completed']
        output = f"📋 TASKS ({len(pending)} pending)\n{'─'*40}\n"
        for t in pending:
            due = t.get('due', '')[:10] if t.get('due') else 'No due'
            output += f"  ⬜ {t['title']} | Due: {due} | ID: {t['id']}\n"
        if show_completed and completed:
            output += "\n✅ DONE:\n"
            for t in completed:
                output += f"  ✅ {t['title']}\n"
        return output
    except Exception as e:
        return f"❌ Error listing tasks: {e}"


@mcp.tool()
def create_task(title: str, tasklist_id: str = "@default", notes: str = "", due_date: str = "") -> str:
    """Create a new task in a task list."""
    try:
        body = {'title': title, 'status': 'needsAction'}
        if notes:
            body['notes'] = notes
        if due_date:
            body['due'] = f"{due_date}T00:00:00.000Z"
        task = _tasks().tasks().insert(tasklist=tasklist_id, body=body).execute()
        return f"✅ Task '{title}' created.\n   🔑 ID: {task['id']}\n   💡 Use ID for update/complete/delete."
    except Exception as e:
        return f"❌ Error creating task: {e}"


@mcp.tool()
def update_task(
    task_id: str,
    tasklist_id: str = "@default",
    title: str = "",
    notes: str = "",
    due_date: str = "",
) -> str:
    """Update a task (title, notes, due date) without completing it."""
    task_id = task_id.strip()
    try:
        svc = _tasks()
        task = svc.tasks().get(tasklist=tasklist_id, task=task_id).execute()
        if title:
            task['title'] = title
        if notes:
            task['notes'] = notes
        if due_date:
            task['due'] = f"{due_date}T00:00:00.000Z"
        updated = svc.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
        return f"✅ Task updated: '{updated['title']}'."
    except Exception as e:
        return f"❌ Error updating task: {e}"


@mcp.tool()
def set_task_due_date(task_id: str, due_date: str, tasklist_id: str = "@default") -> str:
    """Set or change the due date for a task."""
    task_id = task_id.strip()
    return update_task(task_id, tasklist_id, due_date=due_date)


@mcp.tool()
def complete_task(task_id: str, tasklist_id: str = "@default") -> str:
    """Mark a task as completed."""
    task_id = task_id.strip()
    try:
        svc = _tasks()
        task = svc.tasks().get(tasklist=tasklist_id, task=task_id).execute()
        task['status'] = 'completed'
        updated = svc.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
        return f"✅ Task '{updated['title']}' completed! 🎉"
    except Exception as e:
        return f"❌ Error completing task: {e}"


@mcp.tool()
def uncomplete_task(task_id: str, tasklist_id: str = "@default") -> str:
    """Reopen a completed task."""
    task_id = task_id.strip()
    try:
        svc = _tasks()
        task = svc.tasks().get(tasklist=tasklist_id, task=task_id).execute()
        task['status'] = 'needsAction'
        task.pop('completed', None)
        updated = svc.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
        return f"✅ Task '{updated['title']}' reopened."
    except Exception as e:
        return f"❌ Error reopening task: {e}"


@mcp.tool()
def delete_task(task_id: str, tasklist_id: str = "@default") -> str:
    """Delete a task."""
    task_id = task_id.strip()
    try:
        _tasks().tasks().delete(tasklist=tasklist_id, task=task_id).execute()
        return f"🗑️ Task deleted (ID: {task_id})."
    except Exception as e:
        return f"❌ Error deleting task: {e}"


@mcp.tool()
def move_task_to_list(task_id: str, source_list_id: str, target_list_id: str) -> str:
    """Move a task from one list to another."""
    task_id = task_id.strip()
    try:
        svc = _tasks()
        task = svc.tasks().get(tasklist=source_list_id, task=task_id).execute()
        body = {k: task[k] for k in ('title', 'notes', 'due', 'status') if k in task}
        new_task = svc.tasks().insert(tasklist=target_list_id, body=body).execute()
        svc.tasks().delete(tasklist=source_list_id, task=task_id).execute()
        return f"✅ Moved '{new_task['title']}' to list {target_list_id}. New ID: {new_task['id']}"
    except Exception as e:
        return f"❌ Error moving task: {e}"


@mcp.tool()
def create_task_list(title: str) -> str:
    """Create a new task list."""
    try:
        result = _tasks().tasklists().insert(body={'title': title}).execute()
        return f"✅ Task list '{title}' created. ID: {result['id']}"
    except Exception as e:
        return f"❌ Error creating task list: {e}"


@mcp.tool()
def rename_task_list(tasklist_id: str, new_title: str) -> str:
    """Rename a task list."""
    try:
        _tasks().tasklists().patch(tasklist=tasklist_id, body={'title': new_title}).execute()
        return f"✅ Task list renamed to '{new_title}'."
    except Exception as e:
        return f"❌ Error renaming task list: {e}"


@mcp.tool()
def delete_task_list(tasklist_id: str) -> str:
    """Delete a task list."""
    try:
        _tasks().tasklists().delete(tasklist=tasklist_id).execute()
        return f"🗑️ Task list deleted (ID: {tasklist_id})."
    except Exception as e:
        return f"❌ Error deleting task list: {e}"


@mcp.tool()
def clear_completed_tasks(tasklist_id: str = "@default") -> str:
    """Clear all completed tasks from a list."""
    task_id = task_id.strip()
    try:
        svc = _tasks()
        tasks = svc.tasks().list(
            tasklist=tasklist_id, showCompleted=True, showHidden=True, maxResults=100
        ).execute().get('items', [])
        completed = [t for t in tasks if t.get('status') == 'completed']
        for t in completed:
            svc.tasks().delete(tasklist=tasklist_id, task=t['id']).execute()
        return f"🧹 Cleared {len(completed)} completed task(s)."
    except Exception as e:
        return f"❌ Error clearing completed tasks: {e}"


@mcp.tool()
def search_tasks(query: str, tasklist_id: str = "@default") -> str:
    """Search for tasks by title within a list."""
    try:
        tasks = _tasks().tasks().list(tasklist=tasklist_id, maxResults=100).execute().get('items', [])
        q = query.lower()
        matches = [t for t in tasks if q in t.get('title', '').lower()]
        if not matches:
            return f"🔍 No tasks matching '{query}'."
        output = f"🔍 TASKS: '{query}'\n{'─'*30}\n"
        for t in matches:
            status = t.get('status', '?')
            output += f"  [{status}] {t['title']} (ID: {t['id']})\n"
        return output
    except Exception as e:
        return f"❌ Error searching tasks: {e}"


if __name__ == "__main__":
    mcp.run(transport='stdio')
