from mcp.server.fastmcp import FastMCP
from google_common import get_service

mcp = FastMCP("Google-Tasks-Tools")


def _tasks():
    return get_service("tasks", "v1")


@mcp.tool()
def google_tasks(
    action: str,
    tasklist_id: str = "@default",
    task_id: str = "",
    title: str = "",
    notes: str = "",
    due_date: str = "",
    show_completed: bool = False,
    source_list_id: str = "",
    target_list_id: str = "",
    query: str = "",
    max_results: int = 50,
) -> str:
    """Manage task items: list, get, search, create, update, complete, uncomplete, delete, move, clear_completed."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _tasks()

        if action_clean in ("list", "list_tasks"):
            tasks = svc.tasks().list(
                tasklist=tasklist_id, showCompleted=show_completed, maxResults=max_results
            ).execute().get("items", [])
            if not tasks:
                return "No tasks found."
            pending = [t for t in tasks if t.get("status") != "completed"]
            completed = [t for t in tasks if t.get("status") == "completed"]
            lines = [f"TASKS ({len(pending)} pending)", "-" * 40]
            for t in pending:
                due = t.get("due", "")[:10] if t.get("due") else "No due"
                lines.append(f"  [PENDING] {t['title']} | Due: {due} | ID: {t['id']}")
            if show_completed and completed:
                lines.append("\nCOMPLETED:")
                for t in completed:
                    lines.append(f"  [DONE] {t['title']} | ID: {t['id']}")
            return "\n".join(lines)

        elif action_clean in ("get", "get_task"):
            if not task_id:
                return "Error: 'task_id' parameter is required."
            t = svc.tasks().get(tasklist=tasklist_id, task=task_id.strip()).execute()
            due = t.get("due", "")[:10] if t.get("due") else "No due date"
            lines = [
                f"Title  : {t.get('title', '')}",
                f"Status : {t.get('status', '')}",
                f"Due    : {due}",
                f"Notes  : {t.get('notes', '')}",
                f"ID     : {t.get('id', '')}",
            ]
            return "\n".join(lines)

        elif action_clean == "search":
            if not query:
                return "Error: 'query' parameter is required to search tasks."
            tasks = svc.tasks().list(tasklist=tasklist_id, maxResults=100).execute().get("items", [])
            q = query.lower()
            matches = [t for t in tasks if q in t.get("title", "").lower()]
            if not matches:
                return f"No tasks matching '{query}'."
            lines = [f"SEARCH: '{query}' - {len(matches)} MATCHES", "-" * 30]
            for t in matches:
                lines.append(f"  [{t.get('status')}] {t['title']} (ID: {t['id']})")
            return "\n".join(lines)

        elif action_clean == "create":
            if not title:
                return "Error: 'title' parameter is required to create task."
            body = {"title": title, "status": "needsAction"}
            if notes:
                body["notes"] = notes
            if due_date:
                body["due"] = f"{due_date}T00:00:00.000Z"
            task = svc.tasks().insert(tasklist=tasklist_id, body=body).execute()
            return f"Task created: '{title}'. ID: {task['id']}"

        elif action_clean in ("update", "patch"):
            if not task_id:
                return "Error: 'task_id' parameter is required."
            task = svc.tasks().get(tasklist=tasklist_id, task=task_id.strip()).execute()
            if title:
                task["title"] = title
            if notes:
                task["notes"] = notes
            if due_date:
                task["due"] = f"{due_date}T00:00:00.000Z"
            updated = svc.tasks().update(tasklist=tasklist_id, task=task_id.strip(), body=task).execute()
            return f"Task updated: '{updated['title']}'."

        elif action_clean in ("complete", "done"):
            if not task_id:
                return "Error: 'task_id' parameter is required."
            task = svc.tasks().get(tasklist=tasklist_id, task=task_id.strip()).execute()
            task["status"] = "completed"
            updated = svc.tasks().update(tasklist=tasklist_id, task=task_id.strip(), body=task).execute()
            return f"Task '{updated['title']}' marked as completed."

        elif action_clean in ("uncomplete", "reopen"):
            if not task_id:
                return "Error: 'task_id' parameter is required."
            task = svc.tasks().get(tasklist=tasklist_id, task=task_id.strip()).execute()
            task["status"] = "needsAction"
            task.pop("completed", None)
            updated = svc.tasks().update(tasklist=tasklist_id, task=task_id.strip(), body=task).execute()
            return f"Task '{updated['title']}' reopened."

        elif action_clean == "delete":
            if not task_id:
                return "Error: 'task_id' parameter is required."
            svc.tasks().delete(tasklist=tasklist_id, task=task_id.strip()).execute()
            return f"Task {task_id} deleted."

        elif action_clean == "move":
            src = source_list_id or tasklist_id
            dst = target_list_id
            if not task_id or not dst:
                return "Error: 'task_id' and 'target_list_id' are required to move task."
            task = svc.tasks().get(tasklist=src, task=task_id.strip()).execute()
            body = {k: task[k] for k in ("title", "notes", "due", "status") if k in task}
            new_task = svc.tasks().insert(tasklist=dst, body=body).execute()
            svc.tasks().delete(tasklist=src, task=task_id.strip()).execute()
            return f"Moved task to list {dst}. New ID: {new_task['id']}"

        elif action_clean == "clear_completed":
            tasks = svc.tasks().list(
                tasklist=tasklist_id, showCompleted=True, showHidden=True, maxResults=100
            ).execute().get("items", [])
            completed = [t for t in tasks if t.get("status") == "completed"]
            for t in completed:
                svc.tasks().delete(tasklist=tasklist_id, task=t["id"]).execute()
            return f"Cleared {len(completed)} completed task(s)."

        else:
            return f"Unknown task action '{action}'. Valid actions: list, get, search, create, update, complete, uncomplete, delete, move, clear_completed."

    except Exception as e:
        return f"Task operation failed: {e}"


@mcp.tool()
def google_task_lists(
    action: str,
    tasklist_id: str = "",
    title: str = "",
) -> str:
    """Manage task lists: list, get, create, rename, delete."""
    action_clean = (action or "").strip().lower()

    try:
        svc = _tasks()

        if action_clean in ("list", "list_task_lists"):
            lists = svc.tasklists().list(maxResults=50).execute().get("items", [])
            if not lists:
                return "No task lists found."
            lines = [f"TASK LISTS - {len(lists)}", "-" * 35]
            for tl in lists:
                lines.append(f"  {tl['title']} (ID: {tl['id']})")
            return "\n".join(lines)

        elif action_clean in ("get", "get_task_list"):
            target_id = tasklist_id or "@default"
            tl = svc.tasklists().get(tasklist=target_id).execute()
            return f"Task List: '{tl.get('title')}', ID: {tl.get('id')}"

        elif action_clean == "create":
            if not title:
                return "Error: 'title' parameter is required to create task list."
            res = svc.tasklists().insert(body={"title": title}).execute()
            return f"Task list '{title}' created. ID: {res['id']}"

        elif action_clean in ("rename", "update"):
            if not tasklist_id or not title:
                return "Error: 'tasklist_id' and 'title' are required to rename task list."
            svc.tasklists().patch(tasklist=tasklist_id.strip(), body={"title": title}).execute()
            return f"Task list {tasklist_id} renamed to '{title}'."

        elif action_clean == "delete":
            if not tasklist_id:
                return "Error: 'tasklist_id' parameter is required to delete."
            svc.tasklists().delete(tasklist=tasklist_id.strip()).execute()
            return f"Task list {tasklist_id} deleted."

        else:
            return f"Unknown task list action '{action}'. Valid actions: list, get, create, rename, delete."

    except Exception as e:
        return f"Task list operation failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
