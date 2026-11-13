import threading
import uuid
import json
from backend import state


# Interaction registry - thread-safe
_interactions = {}
_lock = threading.Lock()


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

    # Block until resolved or timeout (10 min max to prevent zombie threads)
    event.wait(timeout=600)

    with _lock:
        entry = _interactions.pop(interaction_id, None)

    if entry is None:
        return False
    return entry["result"].get("approved", False)


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

    event.wait(timeout=600)

    with _lock:
        entry = _interactions.pop(interaction_id, None)

    if entry is None:
        return "[No response - interaction timed out]"

    result = entry["result"]
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

    event.wait(timeout=600)

    with _lock:
        entry = _interactions.pop(interaction_id, None)

    if entry is None:
        return "skip"
    return entry["result"].get("decision", "skip")


def resolve_interaction(interaction_id: str, response: dict) -> bool:
    """Called by WebSocket when interaction_response arrives. Unblocks the waiting thread. Returns True if found."""
    with _lock:
        entry = _interactions.get(interaction_id)
        if entry is None:
            return False
        entry["result"].update(response)
        entry["event"].set()
    return True


def cancel_all():
    """Unblocks all pending interactions (e.g. when user stops the agent)."""
    with _lock:
        for iid, entry in list(_interactions.items()):
            entry["result"]["cancelled"] = True
            entry["event"].set()
        _interactions.clear()


def has_pending(interaction_id: str = None) -> bool:
    """Check if there are pending interactions."""
    with _lock:
        if interaction_id:
            return interaction_id in _interactions
        return len(_interactions) > 0
