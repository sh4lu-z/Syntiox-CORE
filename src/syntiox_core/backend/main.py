import os
import sys
import json
import time
import uuid
import asyncio
import base64
import re
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from colorama import init, Fore, Style

# Fix Windows console emoji/unicode crash
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from rich.console import Console
    from rich.syntax import Syntax
    rc = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

init(autoreset=True)


from backend import state, event_bus

def get_llm_module():
    import backend.cloud_llm as active_llm
    return active_llm
from backend.executor import analyze_tool_call, execute_tool
from backend import interaction_manager
from backend.session_manager import archive_scratch_files, list_history, load_session, create_new_session_folder, save_chat_history, get_active_session_path, get_active_brain_path


def extract_image_base64(text: str):
    if getattr(state, "VISION_ENABLED", False) == False:
        return None
    matches = re.findall(r'["\']([a-zA-Z]:\\\\[^"\']+\.(?:png|jpg|jpeg|webp))["\']', text, re.IGNORECASE)
    if not matches:
        matches = re.findall(r'([a-zA-Z]:\\\\[^\n\r*?"<>|]+\.(?:png|jpg|jpeg|webp))', text, re.IGNORECASE)
    for match in matches:
        path = match.strip()
        if os.path.exists(path):
            try:
                with open(path, "rb") as img_file:
                    return base64.b64encode(img_file.read()).decode('utf-8')
            except Exception:
                pass
    return None

app = FastAPI(title="Syntiox CORE V2")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from tools.os_utils import BACKGROUND_TASKS

def _bind_bus(loop: asyncio.AbstractEventLoop):
    event_bus.bind(loop, active_connections)
    state.STATE_CALLBACK = lambda msg: sync_broadcast({"event": "state", "agent_id": "main", "status": msg}, loop)
    state.EVENT_CALLBACK = lambda payload: event_bus.publish(payload)


def _flush_task_stream(tid: str, task: dict, stream_name: str, path: str):
    if not path or not os.path.exists(path):
        return ""
    offsets = task.setdefault("offsets", {"stdout": 0, "stderr": 0})
    prev = offsets.get(stream_name, 0)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f_obj:
            f_obj.seek(prev)
            chunk = f_obj.read()
            offsets[stream_name] = f_obj.tell()
    except Exception:
        return ""
    if chunk:
        event_bus.publish({
            "event": "task_output",
            "agent_id": "main",
            "task_id": tid,
            "stream": stream_name,
            "data": chunk,
        })
    return chunk


@app.on_event("startup")
async def startup_watcher():
    _bind_bus(asyncio.get_running_loop())
    try:
        from backend.mcp_runner import sync_mcp_schemas
        await asyncio.to_thread(sync_mcp_schemas)
    except Exception as e:
        print(f"[MCP] Startup schema sync warning: {e}")
    asyncio.create_task(task_watcher_loop())
    asyncio.create_task(udp_discovery_server())


async def task_watcher_loop():
    while True:
        await asyncio.sleep(2)
        try:
            for tid, task in list(BACKGROUND_TASKS.items()):
                if task.get("notified"):
                    continue
                out_path, err_path = task.get("paths", (None, None))
                _flush_task_stream(tid, task, "stdout", out_path)
                _flush_task_stream(tid, task, "stderr", err_path)
                p = task["process"]
                poll = p.poll()
                if poll is not None:
                    task["notified"] = True
                    _flush_task_stream(tid, task, "stdout", out_path)
                    _flush_task_stream(tid, task, "stderr", err_path)

                    stdout, stderr = "", ""
                    if out_path and os.path.exists(out_path):
                        with open(out_path, "r", encoding="utf-8", errors="replace") as f_obj:
                            stdout = f_obj.read()[-2000:]
                    if err_path and os.path.exists(err_path):
                        with open(err_path, "r", encoding="utf-8", errors="replace") as f_obj:
                            stderr = f_obj.read()[-2000:]

                    msg = f"[System Event] Background Task [{tid}] ('{task['command']}') finished (Code {poll}).\nSTDOUT:\n{stdout.strip()}\nSTDERR:\n{stderr.strip()}\nPlease review this output and proceed with your task."

                    event_bus.publish({"event": "task_end", "agent_id": "main", "task_id": tid, "code": poll})
                    await broadcast_message({"event": "system", "agent_id": "main", "message": f"Task {tid} finished, waking up Agent..."})
                    asyncio.create_task(handle_request_async(msg))
        except Exception as e:
            print(f"Watcher error: {e}")


async def udp_discovery_server():
    import socket
    loop = asyncio.get_running_loop()
    _bind_bus(loop)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception:
        pass

    try:
        sock.bind(("0.0.0.0", 9998))
    except OSError as e:
        print(f"UDP discovery bind skipped: {e}")
        sock.close()
        return

    sock.setblocking(False)
    try:
        while True:
            try:
                data, addr = await loop.sock_recvfrom(sock, 1024)
                message = data.decode("utf-8", errors="ignore").strip()

                if message == "SYNTIOX_DISCOVER":
                    reply = b"SYNTIOX_CORE_HERE:9999"
                    await loop.sock_sendto(sock, reply, addr)
            except Exception:
                pass

            await asyncio.sleep(0.1)
    finally:
        sock.close()


active_connections = []


async def broadcast_message(payload):
    if isinstance(payload, dict):
        event_bus.publish(payload)
        return
    message = str(payload)
    dead = []
    for connection in list(active_connections):
        try:
            await asyncio.wait_for(connection.send_text(message), timeout=5.0)
        except Exception:
            dead.append(connection)
    for d in dead:
        if d in active_connections:
            active_connections.remove(d)


def sync_broadcast(payload, loop: asyncio.AbstractEventLoop):
    if loop is not None and not loop.is_closed() and loop.is_running():
        event_bus.bind(loop, active_connections)
    event_bus.publish(payload)

# State variables
chat_history = []
# Summarized view sent to the LLM; chat_history keeps the full log on disk
chat_context = []
current_session_title = "Untitled Session"
current_session_id = None
_request_lock = None


def _get_request_lock() -> asyncio.Lock:
    global _request_lock
    if _request_lock is None:
        _request_lock = asyncio.Lock()
    return _request_lock

def save_agent_loop_log(loop_history, command):
    active_path = get_active_session_path()
    if not active_path or not loop_history:
        return
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(active_path, f"agent_loop_{timestamp}.log")
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"=== Agent Loop Log ===\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"User Command: {command}\n\n")
            for step in loop_history:
                f.write(f"--- Step {step.get('step', '?')} ---\n")
                if step.get("thinking"):
                    f.write(f"Native Thinking: {step.get('thinking', '').strip()}\n")
                f.write(f"Thought: {step.get('thought', '').strip()}\n")
                
                tool_calls = step.get('tool_calls', [])
                if tool_calls:
                    f.write(f"\nTools Called:\n")
                    for tc in tool_calls:
                        f.write(f" - {tc.get('function', {}).get('name', 'unknown')}: {json.dumps(tc.get('function', {}).get('arguments', {}))}\n")
                        
                f.write(f"\nExecution Result:\n{step.get('execution_result', '').strip()}\n")
                f.write(f"{'='*40}\n\n")
    except Exception as e:
        print(f"[Warning] Could not save agent loop log: {e}")

_FILE_WRITE_TOOLS = frozenset({
    "write_to_file",
    "write_file",
    "replace_file_content",
    "edit_file",
    "append_to_file",
    "multi_replace_file_content",
})


def _is_tool_ok(output: str) -> bool:
    text = (output or "").lstrip()
    return not text.startswith((
        "Error:",
        "Error executing",
        "Command Failed",
        "Command timed out",
        "Action blocked",
    ))


def run_agent_loop_sync(command: str, history_str: str, loop: asyncio.AbstractEventLoop, image_base64: str = None) -> str:
    ctx = {"text": "", "thinking": "", "state": "Thinking"}
    run_t0 = time.time()
    own_run = event_bus.get_run() is None
    if own_run:
        event_bus.set_run(uuid.uuid4().hex[:12])
    finished = False

    def finish_run(outcome: str, content: str) -> str:
        nonlocal finished
        finished = True
        event_bus.set_step(None)
        sync_broadcast({
            "event": "run_end",
            "agent_id": "main",
            "outcome": outcome,
            "content": content,
            "duration_ms": round((time.time() - run_t0) * 1000),
        }, loop)
        return content

    def thought_callback(chunk):
        ctx["thinking"] += chunk
        if ctx["state"] != "Thinking":
            ctx["state"] = "Thinking"
            sync_broadcast({"event": "state", "agent_id": "main", "status": "Thinking"}, loop)
        sync_broadcast({"event": "thinking", "agent_id": "main", "data": chunk}, loop)
        sys.stdout.write(f"{Fore.LIGHTBLACK_EX}{chunk}{Style.RESET_ALL}")
        sys.stdout.flush()

    def stream_callback(token):
        ctx["text"] += token

        # Simply broadcast raw tokens to the frontend
        sync_broadcast({"event": "token", "agent_id": "main", "data": token}, loop)
        sys.stdout.write(token)
        sys.stdout.flush()

        # Update socket state
        new_state = ctx["state"]
        text_lower = ctx["text"].lower()
        if "<scratchpad>" in text_lower and "</scratchpad>" not in text_lower:
            new_state = "Planning"
        elif "[code generated]" in text_lower or "```" in text_lower:
            new_state = "Code Generating"
        elif new_state == "Thinking":
            new_state = "Responding"

        if new_state != ctx["state"]:
            ctx["state"] = new_state
            sync_broadcast({"event": "state", "agent_id": "main", "status": new_state}, loop)

    sync_broadcast({
        "event": "run_start",
        "agent_id": "main",
        "command": command,
        "session_id": current_session_id,
    }, loop)
    sync_broadcast({"event": "state", "agent_id": "main", "status": "Thinking"}, loop)
    print(f"{Fore.GREEN}[Syntiox CORE] Starting Agent Loop for task: '{command}'{Style.RESET_ALL}")

    loop_history = []
    max_steps = 30
    current_step = 1
    consecutive_recoveries = 0
    loop_memory = get_llm_module()._init_loop_memory()

    try:
        while current_step <= max_steps:
            if getattr(state, "STOP_REQUESTED", False):
                interaction_manager.cancel_all()
                sync_broadcast({"event": "system", "agent_id": "main", "message": "Agent loop stopped by user"}, loop)
                save_agent_loop_log(loop_history, command)
                return finish_run("stopped", "Agent stopped by user.")

            event_bus.set_step(current_step)
            step_t0 = time.time()
            sync_broadcast({
                "event": "step_start",
                "agent_id": "main",
                "step": current_step,
                "max_steps": max_steps,
            }, loop)

            def emit_step_end(s_data=None):
                s_data = s_data if isinstance(s_data, dict) else {}
                sync_broadcast({
                    "event": "step_end",
                    "agent_id": "main",
                    "step": current_step,
                    "model": s_data.get("model"),
                    "usage": s_data.get("usage"),
                    "finish_reason": s_data.get("finish_reason"),
                    "duration_ms": round((time.time() - step_t0) * 1000),
                }, loop)

            def tool_call_callback(phase, index, name, data, call_id=None):
                effective_id = call_id or f"step_{current_step}_call_{index}"
                if phase == "delta":
                    if name in _FILE_WRITE_TOOLS and ctx["state"] != "Code Generating":
                        ctx["state"] = "Code Generating"
                        sync_broadcast({"event": "state", "agent_id": "main", "status": "Code Generating"}, loop)
                    sync_broadcast({
                        "event": "tool_call_delta",
                        "agent_id": "main",
                        "index": index,
                        "call_id": effective_id,
                        "name": name,
                        "args_delta": data,
                    }, loop)
                elif phase == "detected":
                    if name in _FILE_WRITE_TOOLS and ctx["state"] != "Code Generating":
                        ctx["state"] = "Code Generating"
                        sync_broadcast({"event": "state", "agent_id": "main", "status": "Code Generating"}, loop)
                    sync_broadcast({
                        "event": "tool_call_detected",
                        "agent_id": "main",
                        "index": index,
                        "call_id": effective_id,
                        "name": name,
                        "args": data,
                    }, loop)

            print(f"{Fore.GREEN}[Syntiox CORE] --- Agent Loop Step {current_step} ---{Style.RESET_ALL}")
            task_list_str = ""
            brain_path = get_active_brain_path()
            if brain_path:
                brain_task = os.path.join(brain_path, "task.md")
                if os.path.exists(brain_task):
                    try:
                        with open(brain_task, "r", encoding="utf-8") as f:
                            task_list_str = f.read()
                    except Exception:
                        pass

            ctx["text"] = ""
            ctx["thinking"] = ""
            ctx["state"] = "Thinking"
            sync_broadcast({"event": "state", "agent_id": "main", "status": "Thinking"}, loop)
            print(f"{Fore.GREEN}[Syntiox CORE] Processing... (This might take a moment){Style.RESET_ALL}")

            kwargs = {
                "image_base64": image_base64,
                "loop_memory": loop_memory,
                "thought_callback": thought_callback,
                "tool_call_callback": tool_call_callback,
            }
            step_data = get_llm_module().generate_agent_step(command, loop_history, current_step, history_str, task_list_str, stream_callback=stream_callback, **kwargs)

            sys.stdout.write(f"{Style.RESET_ALL}\n")
            sys.stdout.flush()

            if "error" in step_data:
                emit_step_end(step_data)
                save_agent_loop_log(loop_history, command)
                return finish_run("error", "Task failed due to error: " + step_data["error"])

            thought = step_data.get("thought", "")
            thinking = step_data.get("thinking", "")
            tool_calls = step_data.get("tool_calls", [])
            status = step_data.get("status", "CONTINUE")

            if tool_calls:
                for tool in tool_calls:
                    t_name = tool.get("function", {}).get("name", "")
                    t_args = tool.get("function", {}).get("arguments", {})
                    if RICH_AVAILABLE:
                        console_text = f"[bold cyan]EXECUTING TOOL:[/bold cyan] [bold white]{t_name}[/bold white]"
                        rc.print(console_text)
                        for k, v in t_args.items():
                            val_str = str(v)
                            rc.print(f"[bold cyan] - {k.upper()}:[/bold cyan]")
                            if k in ["command", "content", "code", "file_content", "code_content", "replacementContent"]:
                                syntax = Syntax(val_str, "html" if "<html" in val_str else "python", theme="monokai", word_wrap=True)
                                rc.print(syntax)
                            else:
                                rc.print(f"[white]{val_str}[/white]")
                        print("\n")
                    else:
                        print(f"\n{Fore.CYAN}EXECUTING TOOL: {Fore.WHITE}{t_name}")
                        for k, v in t_args.items():
                            val_str = str(v)
                            print(f"{Fore.CYAN} - {k.upper()}: {Fore.WHITE}{val_str}{Style.RESET_ALL}")
                        print("\n")

            if not thought and not thinking and not tool_calls and status == "CONTINUE":
                emit_step_end(step_data)
                save_agent_loop_log(loop_history, command)
                return finish_run("error", "Task failed: Agent returned an empty or invalid response.")

            execution_result = ""

            if not tool_calls and status == "COMPLETE":
                final_msg = step_data.get("final_message", "")

                if re.search(r"<next_step_required\s*/>", final_msg, re.IGNORECASE):
                    status = "CONTINUE"
                    execution_result = "System: You requested to continue to the next step. Proceed."
                    tool_calls = [{"function": {"name": "system_continue", "arguments": {}}}]
                elif "[SYSTEM_RECOVERY_REQUIRED]" in final_msg:
                    consecutive_recoveries += 1
                    if consecutive_recoveries >= 3:
                        sync_broadcast({"event": "state", "agent_id": "main", "status": "Recovery limit reached, forcing text-only response..."}, loop)
                        print(f"{Fore.RED}[Syntiox CORE] Recovery limit reached ({consecutive_recoveries}). Forcing text-only completion.{Style.RESET_ALL}")
                        tool_calls = [{"function": {"name": "system_recovery", "arguments": {}}}]
                        execution_result = "SYSTEM OVERRIDE: You have failed to call tools correctly 3 times in a row. STOP trying to use tools. Instead, provide your complete response as plain text. If you were trying to write code, output it inside markdown code blocks. Then add <task_complete /> to finish."
                        status = "CONTINUE"
                    else:
                        sync_broadcast({"event": "state", "agent_id": "main", "status": "Recovering from malformed tool call..."}, loop)
                        print(f"{Fore.YELLOW}[Syntiox CORE] Model generated a malformed API response (attempt {consecutive_recoveries}/3). Retrying...{Style.RESET_ALL}")
                        tool_calls = [{"function": {"name": "system_recovery", "arguments": {}}}]
                        execution_result = "CRITICAL ERROR: The API blocked your function call because it was malformed (likely invalid JSON, unescaped quotes, or output too large). DO NOT try to write massive files in a single tool call. Break your action into smaller chunks (e.g. write small pieces using append/replace tools) and try again."
                        status = "CONTINUE"

                elif (
                    (thinking.strip() and not final_msg.strip())
                    or ("<scratchpad>" in final_msg.lower() and not re.search(r"<task_complete\s*/>", final_msg, re.IGNORECASE))
                ):

                    consecutive_recoveries += 1

                    if consecutive_recoveries >= 3:
                        sync_broadcast({"event": "state", "agent_id": "main", "status": "Recovery limit reached, forcing text-only response..."}, loop)
                        print(f"{Fore.RED}[Syntiox CORE] Recovery limit reached ({consecutive_recoveries}). Forcing text-only completion.{Style.RESET_ALL}")

                        tool_calls = [{"function": {"name": "system_recovery", "arguments": {}}}]
                        execution_result = "SYSTEM OVERRIDE: You have failed to call tools correctly 3 times in a row. STOP trying to use tools. Instead, provide your complete response as plain text. If you were trying to write code, output it inside markdown code blocks. Then add <task_complete /> to finish."
                        status = "CONTINUE"
                    else:
                        sync_broadcast({"event": "state", "agent_id": "main", "status": "Recovering from missing tool call..."}, loop)
                        print(f"{Fore.YELLOW}[Syntiox CORE] Model dropped tool call payload (attempt {consecutive_recoveries}/3). Retrying...{Style.RESET_ALL}")

                        tool_calls = [{"function": {"name": "system_recovery", "arguments": {}}}]
                        execution_result = "CRITICAL: Your tool call was NOT executed because you output it as text instead of using the Native Function Calling API. You MUST use the function_call mechanism provided by the API, not XML tags or text. Try again now."
                        status = "CONTINUE"
                else:
                    consecutive_recoveries = 0

            if tool_calls:
                all_execution_results = []

                for idx, tool in enumerate(tool_calls):
                    tool_name = tool["function"]["name"]
                    tool_args = tool["function"]["arguments"]
                    call_id = tool.get("call_id") or f"step_{current_step}_call_{idx}"
                    tool["call_id"] = call_id

                    requires_approval = analyze_tool_call(tool_name, tool_args)
                    if requires_approval:
                        sync_broadcast({"event": "state", "agent_id": "main", "status": f"Awaiting approval for {tool_name}"}, loop)
                        approved = interaction_manager.request_approval(
                            agent_id="main",
                            tool_name=tool_name,
                            tool_args=tool_args,
                        )
                        if not approved:
                            single_result = f"Action blocked: User denied permission to execute '{tool_name}'."
                            tool["result"] = single_result
                            all_execution_results.append(f"[Tool: {tool_name} Result]:\n{single_result}")
                            sync_broadcast({
                                "event": "tool_result",
                                "agent_id": "main",
                                "tool": tool_name,
                                "call_id": call_id,
                                "ok": False,
                                "duration_ms": 0,
                                "output": single_result,
                            }, loop)
                            if RICH_AVAILABLE:
                                rc.print(f"\n[bold red]DENIED - {tool_name}[/bold red]")
                            else:
                                print(f"\n{Fore.RED}[DENIED - {tool_name}]{Style.RESET_ALL}")
                            continue

                    if tool_name not in ["system_recovery", "system_continue"]:
                        sync_broadcast({"event": "state", "agent_id": "main", "status": f"Running {tool_name}"}, loop)
                        sync_broadcast({"event": "tool_call", "agent_id": "main", "tool": tool_name, "args": tool_args, "call_id": call_id}, loop)

                    time.sleep(0.15)

                    tool_t0 = time.time()
                    if tool_name in ["system_recovery", "system_continue"]:
                        single_result = execution_result
                    else:
                        event_bus.push_tool(call_id, tool_name)
                        try:
                            single_result = execute_tool(tool_name, tool_args)
                        finally:
                            event_bus.pop_tool()
                        consecutive_recoveries = 0
                    tool_duration_ms = round((time.time() - tool_t0) * 1000)
                    # Per-call result so each function response gets its own output
                    tool["result"] = single_result

                    ui_tool_name = tool_name
                    ui_result = str(single_result)
                    m = re.search(r'\[ACTION_START\] Tool: (.*?)\n', ui_result)
                    if m:
                        ui_tool_name = m.group(1).strip()
                    ui_result = ui_result.replace(f"[ACTION_START] Tool: {ui_tool_name}\n", "")
                    ui_result = re.sub(r'\[ACTION_CMD\].*?\n', '', ui_result)
                    ui_result = ui_result.replace("[ACTION_END]", "").strip()

                    if tool_name not in ["system_recovery", "system_continue"]:
                        sync_broadcast({
                            "event": "tool_result",
                            "agent_id": "main",
                            "tool": ui_tool_name,
                            "call_id": call_id,
                            "ok": _is_tool_ok(ui_result),
                            "duration_ms": tool_duration_ms,
                            "output": ui_result,
                        }, loop)
                    if RICH_AVAILABLE:
                        rc.print(f"\n[bold magenta]EXECUTION RESULT - {tool_name}[/bold magenta]")
                        rc.print(f"[magenta]{str(single_result)}[/magenta]")
                    else:
                        print(f"\n{Fore.MAGENTA}[EXECUTION RESULT - {tool_name}]\n{single_result}{Style.RESET_ALL}")

                    all_execution_results.append(f"[Tool: {tool_name} Result]:\n{single_result}")

                    if getattr(state, "VISION_ENABLED", False):
                        img_match = re.search(r'\[IMAGE_RESULT\]\s*(.+?\.(png|jpg|jpeg|webp))', str(single_result), re.IGNORECASE)
                        if img_match:
                            img_path = img_match.group(1).strip()
                            if os.path.exists(img_path):
                                try:
                                    with open(img_path, "rb") as f:
                                        image_base64 = base64.b64encode(f.read()).decode('utf-8')
                                    print(f"{Fore.CYAN}[Syntiox CORE] Captured Visual Feedback from: {img_path}{Style.RESET_ALL}")
                                except Exception as e:
                                    print(f"{Fore.RED}[Syntiox CORE] Failed to read image result: {e}{Style.RESET_ALL}")

                execution_result = "\n\n".join(all_execution_results)

            emit_step_end(step_data)

            loop_history.append({
                "step": current_step,
                "thought": thought,
                "thinking": thinking,
                "tool_calls": tool_calls,
                "execution_result": execution_result
            })

            if status == "COMPLETE":
                print(f"{Fore.GREEN}[Syntiox CORE] Task fully completed!{Style.RESET_ALL}")
                msg = step_data.get("final_message", "Task fully completed successfully.").strip()
                msg = re.sub(r"<task_complete\s*/>", "", msg, flags=re.IGNORECASE).strip()

                if not msg:
                    msg = "Task completed successfully."

                save_agent_loop_log(loop_history, command)
                outcome = "stopped" if getattr(state, "STOP_REQUESTED", False) else "complete"
                return finish_run(outcome, msg)

            current_step += 1

        save_agent_loop_log(loop_history, command)
        return finish_run("step_limit", "Task could not be completed within the step limit.")
    finally:
        if not finished:
            finish_run("error", "Agent loop terminated unexpectedly.")
        elif event_bus.get_step() is not None:
            event_bus.set_step(None)
        if own_run:
            event_bus.set_run(None)


async def _handle_request_async_with_run(command: str):
    async with _get_request_lock():
        return await _handle_request_locked(command)


async def handle_request_async(command: str):
    _, response = await _handle_request_async_with_run(command)
    return response


async def _handle_request_locked(command: str):
    global chat_history, chat_context, current_session_title, current_session_id
    loop = asyncio.get_running_loop()
    _bind_bus(loop)

    state.STOP_REQUESTED = False

    cmd_lower = command.strip().lower()

    if cmd_lower == "/history":
        return None, list_history()

    if cmd_lower.startswith("/load "):
        if current_session_id:
            archive_scratch_files(current_session_id)
        session_id_str = cmd_lower.split("/load ")[1].strip()
        try:
            session_id_int = int(session_id_str)
        except ValueError:
            return None, "Invalid session ID. Please use a numeric ID."
        history, msg = load_session(session_id_str)
        if history is not None:
            chat_history = history
            chat_context = await asyncio.to_thread(get_llm_module().summarize_memory, list(history))
            current_session_id = session_id_int
            current_session_title = f"Loaded Session {session_id_str}"
            event_bus.publish({
                "event": "session",
                "agent_id": "main",
                "session_id": current_session_id,
                "title": current_session_title,
            })
        return None, msg

    if cmd_lower == "/new":
        if current_session_id:
            archive_scratch_files(current_session_id)
        chat_history = []
        chat_context = []
        current_session_title = "Untitled Session"
        current_session_id = None
        try:
            from backend.session_manager import set_active_brain_path
            set_active_brain_path(None)
        except Exception:
            pass
        event_bus.publish({
            "event": "session",
            "agent_id": "main",
            "session_id": None,
            "title": current_session_title,
        })
        return None, "All previous conversation history and tasks have been safely archived to the history folder! We are starting fresh."

    run_id = uuid.uuid4().hex[:12]
    event_bus.set_run(run_id)
    event_bus.set_step(None)
    try:
        if not chat_history:
            current_session_title = await asyncio.to_thread(get_llm_module().generate_session_title, command)
            current_session_id = create_new_session_folder(current_session_title)
            event_bus.publish({
                "event": "session",
                "agent_id": "main",
                "session_id": current_session_id,
                "title": current_session_title,
            })

        chat_history.append(f"User: {command}")
        chat_context.append(f"User: {command}")
        save_chat_history(current_session_id, chat_history)
        history_str = "\n".join(chat_context)

        img_b64 = extract_image_base64(command)
        final_message = await asyncio.to_thread(run_agent_loop_sync, command, history_str, loop, img_b64)
        chat_history.append(f"Syntiox CORE: {final_message}")
        chat_context.append(f"Syntiox CORE: {final_message}")
        chat_context = await asyncio.to_thread(get_llm_module().summarize_memory, chat_context)
        save_chat_history(current_session_id, chat_history)
        return run_id, final_message
    finally:
        event_bus.set_step(None)
        event_bus.set_run(None)


async def _run_command_task(command: str, target_ws: WebSocket):
    try:
        run_id, response = await _handle_request_async_with_run(command)
    except Exception as e:
        run_id = None
        response = f"Error processing request: {e}"
    event_bus.publish({
        "event": "final",
        "agent_id": "main",
        "run_id": run_id,
        "step": None,
        "content": response,
    }, target=target_ws)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    await websocket.accept()

    client_ip = websocket.client.host if websocket.client else "unknown"
    is_localhost = client_ip in ("127.0.0.1", "::1", "localhost", "0:0:0:0:0:0:0:1", "testclient")

    if not is_localhost:
        expected_token = os.environ.get("SYNTIOX_AUTH_TOKEN")
        if not expected_token or token != expected_token:
            print(f"{Fore.RED}[Security] Rejected unauthorized connection from {client_ip}.{Style.RESET_ALL}")
            await websocket.close(code=1008)
            return

    active_connections.append(websocket)
    _bind_bus(asyncio.get_running_loop())
    try:
        while True:
            data = await websocket.receive_text()

            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = {"command": data}

            action = payload.get("action")

            if action == "stop":
                state.STOP_REQUESTED = True
                interaction_manager.cancel_all()
                continue

            if action == "interaction_response":
                iid = payload.get("interaction_id", "")
                interaction_manager.resolve_interaction(iid, payload)
                continue

            if action == "get_workspace":
                event_bus.publish({"event": "workspace_changed", **state.get_workspace_info()}, target=websocket)
                continue

            if action == "set_workspace":
                ws_path = payload.get("path") if "path" in payload else payload.get("workspace")
                ok, result_msg = state.set_workspace_dir(ws_path)
                if ok:
                    await broadcast_message({"event": "workspace_changed", **state.get_workspace_info()})
                else:
                    event_bus.publish({
                        "event": "system",
                        "agent_id": "main",
                        "message": result_msg,
                    }, target=websocket)
                    event_bus.publish({"event": "workspace_changed", **state.get_workspace_info()}, target=websocket)
                continue

            if "workspace" in payload:
                ws_val = payload.get("workspace")
                if ws_val != state.WORKSPACE_DIR:
                    ok, _ = state.set_workspace_dir(ws_val)
                    if ok:
                        await broadcast_message({"event": "workspace_changed", **state.get_workspace_info()})

            command = payload.get("command", "")
            asyncio.create_task(_run_command_task(command, websocket))
    except Exception:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        if len(active_connections) == 0:
            state.STOP_REQUESTED = True
            interaction_manager.cancel_all()


@app.get("/stop")
def stop_generation():
    state.STOP_REQUESTED = True
    interaction_manager.cancel_all()
    return {"status": "stopping"}


@app.get("/ping")
def ping_server(request: Request):
    client_ip = request.client.host
    print(f"[{client_ip}] Network Discovery Ping Received!")
    return {"status": "SYNTIOX_CORE_HERE", "protocol": 2}
