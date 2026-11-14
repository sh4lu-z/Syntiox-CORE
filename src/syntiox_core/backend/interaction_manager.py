import threading
import uuid
import json
from backend import state


# Interaction registry - thread-safe
_interactions = {}
_lock = threading.Lock()


def _emit_resolved(interaction_id: str, agent_id: str, outcome: str):
    state.emit_event({
        "event": "interaction_resolved",
        "agent_id": agent_id,
        "interaction_id": interaction_id,
        "outcome": outcome,
    })


def _wait_for_interaction(interaction_id: str, event: threading.Event):
    signaled = event.wait(timeout=600)
    with _lock:
        entry = _interactions.pop(interaction_id, None)
    if entry is None:
        return None
    if not signaled and entry.get("outcome") is None:
        _emit_resolved(interaction_id, entry["agent_id"], "timeout")
        return None
    return entry["result"]


def request_approval(agent_id: str, tool_name: str, tool_args: dict, reason: str = "") -> bool:
    """Blocks calling thread until client approves or denies. Returns True if approved."""
    interaction_id = str(uuid.uuid4())
    event = threading.Event()
    result_holder = {"approved": False}

    with _lock:
        _interactions[interaction_id] = {
            "event": event,
            "result": result_holder,
            "type": "approval",
            "agent_id": agent_id,
            "outcome": None,
        }

    state.emit_event({
        "event": "interaction_required",
        "interaction_id": interaction_id,
        "interaction_type": "approval",
        "agent_id": agent_id,
        "payload": {
            "tool": tool_name,
            "args": tool_args,
            "risk": reason or "This action may modify your system or files outside the scratch folder.",
        },
    })

    result = _wait_for_interaction(interaction_id, event)
    if result is None:
        return False
    return result.get("approved", False)


def request_user_input(
    agent_id: str,
    question: str,
    options: list = None,
    is_multi_select: bool = False,
    allow_custom: bool = True,
) -> str:
    """Blocks calling thread until client submits a response. Returns the user's answer as a string."""
    interaction_id = str(uuid.uuid4())
    event = threading.Event()
    result_holder = {"response": ""}

    with _lock:
        _interactions[interaction_id] = {
            "event": event,
            "result": result_holder,
            "type": "question",
            "agent_id": agent_id,
            "outcome": None,
        }

    state.emit_event({
        "event": "interaction_required",
        "interaction_id": interaction_id,
        "interaction_type": "question",
        "agent_id": agent_id,
        "payload": {
            "question": question,
            "options": options,
            "is_multi_select": is_multi_select,
            "allow_custom": allow_custom,
        },
    })

    result = _wait_for_interaction(interaction_id, event)
    if result is None:
        return "[No response - interaction timed out]"

    # Build a clean string from the response
    selected = result.get("selected")
    custom = result.get("custom_text", "")
    if selected:
        return ", ".join(selected) + (f" ({custom})" if custom else "")
    if custom:
        return custom
    return result.get("response", "[No response]")


def request_mcp_permission(agent_id: str, server_name: str, tool_name: str, tool_args: dict) -> str:
    """Blocks calling thread until client responds with 'run', 'allow_always', or 'skip'."""
    interaction_id = str(uuid.uuid4())
    event = threading.Event()
    result_holder = {"decision": "skip"}

    with _lock:
        _interactions[interaction_id] = {
            "event": event,
            "result": result_holder,
            "type": "mcp_permission",
            "agent_id": agent_id,
            "outcome": None,
        }

    state.emit_event({
        "event": "interaction_required",
        "interaction_id": interaction_id,
        "interaction_type": "mcp_permission",
        "agent_id": agent_id,
        "payload": {
            "server": server_name,
            "tool": tool_name,
            "args": tool_args,
        },
    })

    result = _wait_for_interaction(interaction_id, event)
    if result is None:
        return "skip"
    return result.get("decision", "skip")


def resolve_interaction(interaction_id: str, response: dict) -> bool:
    """Called by WebSocket when interaction_response arrives. Unblocks the waiting thread. Returns True if found."""
    agent_id = None
    with _lock:
        entry = _interactions.get(interaction_id)
        if entry is None:
            return False
        agent_id = entry.get("agent_id", "main")
        entry["outcome"] = "resolved"
        entry["result"].update(response)
        entry["event"].set()
    _emit_resolved(interaction_id, agent_id, "resolved")
    return True


def cancel_all():
    """Unblocks all pending interactions (e.g. when user stops the agent)."""
    cancelled = []
    with _lock:
        for iid, entry in list(_interactions.items()):
            entry["outcome"] = "cancelled"
            entry["result"]["cancelled"] = True
            entry["event"].set()
            cancelled.append((iid, entry.get("agent_id", "main")))
        _interactions.clear()
    for iid, agent_id in cancelled:
        _emit_resolved(iid, agent_id, "cancelled")


def has_pending(interaction_id: str = None) -> bool:
    """Check if there are pending interactions."""
    with _lock:
        if interaction_id:
            return interaction_id in _interactions
        return len(_interactions) > 0
