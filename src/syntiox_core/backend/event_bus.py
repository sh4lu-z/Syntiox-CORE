import asyncio
import itertools
import json
import os
import threading
import time

_seq = itertools.count(1)
_seq_lock = threading.Lock()
_ctx_lock = threading.Lock()
_loop = None
_queue = None
_dispatcher = None
_connections = None
_ctx = {"run_id": None, "step": None}
_local = threading.local()

_raw_max = os.getenv("WS_MAX_FIELD_CHARS", "200000")
MAX_FIELD_CHARS = int(_raw_max) if _raw_max.strip() else 0

_NON_CAP_KEYS = frozenset({
    "event",
    "agent_id",
    "run_id",
    "call_id",
    "tool",
    "name",
    "stream",
    "outcome",
    "reason",
    "provider",
    "model",
    "phase",
    "action",
    "scope",
    "method",
    "status",
    "url",
    "title",
    "interaction_id",
    "interaction_type",
    "finish_reason",
})


def _ensure_dispatcher(loop: asyncio.AbstractEventLoop):
    global _dispatcher
    if _loop is not loop or _queue is None:
        return
    if _dispatcher is None or _dispatcher.done():
        _dispatcher = loop.create_task(_dispatch(_queue))


def bind(loop: asyncio.AbstractEventLoop, connections):
    """Bind the bus to an event loop and client list, starting the dispatcher lazily."""
    global _loop, _queue, _dispatcher, _connections
    with _seq_lock:
        if _loop is not loop:
            _loop = loop
            _queue = asyncio.Queue()
            _dispatcher = None
        _connections = connections

    if loop is None or loop.is_closed() or not loop.is_running():
        return

    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is loop:
        _ensure_dispatcher(loop)
    else:
        try:
            loop.call_soon_threadsafe(_ensure_dispatcher, loop)
        except RuntimeError:
            pass


def set_run(run_id: str = None):
    with _ctx_lock:
        _ctx["run_id"] = run_id


def get_run():
    with _ctx_lock:
        return _ctx["run_id"]


def set_step(step: int = None):
    with _ctx_lock:
        _ctx["step"] = step


def get_step():
    with _ctx_lock:
        return _ctx["step"]


def push_agent(agent_id: str):
    stack = getattr(_local, "agent_stack", None)
    if stack is None:
        stack = []
        _local.agent_stack = stack
    stack.append(agent_id)


def pop_agent():
    stack = getattr(_local, "agent_stack", None)
    if stack:
        return stack.pop()
    return None


def current_agent() -> str:
    stack = getattr(_local, "agent_stack", None)
    if stack:
        return stack[-1]
    return "main"


def push_tool(call_id: str = None, tool: str = None):
    stack = getattr(_local, "tool_stack", None)
    if stack is None:
        stack = []
        _local.tool_stack = stack
    stack.append((call_id, tool))


def pop_tool():
    stack = getattr(_local, "tool_stack", None)
    if stack:
        return stack.pop()
    return None


def current_tool() -> tuple:
    stack = getattr(_local, "tool_stack", None)
    if stack:
        return stack[-1]
    return (None, None)


def cap(value, limit: int = None):
    """Truncate a string above the char limit, returning (value, truncated)."""
    max_chars = MAX_FIELD_CHARS if limit is None else limit
    if max_chars <= 0 or not isinstance(value, str) or len(value) <= max_chars:
        return value, False
    suffix = f"\n...[truncated {len(value) - max_chars} chars]"
    if max_chars <= len(suffix):
        return value[:max_chars], True
    return value[: max_chars - len(suffix)] + suffix, True


def _cap_value(value, key: str = None, limit: int = None):
    if key in _NON_CAP_KEYS:
        return value, False
    if isinstance(value, str):
        return cap(value, limit)
    if isinstance(value, dict):
        changed = False
        out = {}
        for k, v in value.items():
            nv, t = _cap_value(v, k, limit)
            if t or nv is not v:
                changed = True
            out[k] = nv
        return (out if changed else value), changed
    if isinstance(value, list):
        changed = False
        out = []
        for item in value:
            nv, t = _cap_value(item, None, limit)
            if t or nv is not item:
                changed = True
            out.append(nv)
        return (out if changed else value), changed
    return value, False


def _cap_payload(payload: dict, limit: int = None) -> dict:
    out = {}
    any_truncated = bool(payload.get("truncated"))
    for k, v in payload.items():
        nv, t = _cap_value(v, k, limit)
        if t:
            any_truncated = True
        out[k] = nv
    if any_truncated:
        out["truncated"] = True
    elif out.get("event") == "tool_result":
        out["truncated"] = False
    return out


async def _dispatch(queue: asyncio.Queue):
    while True:
        target, message = await queue.get()
        try:
            targets = [target] if target is not None else list(_connections or ())
            dead = []
            for conn in targets:
                try:
                    await asyncio.wait_for(conn.send_text(message), timeout=5.0)
                except Exception:
                    dead.append(conn)
            if dead and _connections is not None:
                for conn in dead:
                    if conn in _connections:
                        _connections.remove(conn)
        finally:
            queue.task_done()


def publish(payload: dict, target=None):
    """Attach the v2 envelope, cap large fields, and enqueue in strict sequence order."""
    if not isinstance(payload, dict):
        return None

    enriched = dict(payload)
    enriched.setdefault("agent_id", current_agent())
    enriched["ts"] = round(time.time(), 3)
    with _ctx_lock:
        enriched.setdefault("run_id", _ctx["run_id"])
        enriched.setdefault("step", _ctx["step"])

    capped = _cap_payload(enriched)

    with _seq_lock:
        loop = _loop
        queue = _queue
        conns = _connections
        if loop is None or loop.is_closed() or not loop.is_running() or queue is None:
            return None
        if target is None and not conns:
            return None
        capped["seq"] = next(_seq)
        message = json.dumps(capped, ensure_ascii=False)
        try:
            loop.call_soon_threadsafe(queue.put_nowait, (target, message))
        except RuntimeError:
            return None
    return capped


async def drain():
    """Wait until all currently scheduled bus events have been dispatched."""
    with _seq_lock:
        loop = _loop
        queue = _queue
        if loop is None or loop.is_closed() or not loop.is_running() or queue is None:
            return
        marker = loop.create_future()
        try:
            loop.call_soon_threadsafe(lambda: marker.set_result(None) if not marker.done() else None)
        except RuntimeError:
            return
    await marker
    await queue.join()
