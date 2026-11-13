import os
import sys
import json
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


from backend import state

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

@app.on_event("startup")
async def startup_watcher():
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
                p = task["process"]
                poll = p.poll()
                if poll is not None:
                    task["notified"] = True
                    
                    out_path, err_path = task.get("paths", (None, None))
                    stdout, stderr = "", ""
                    if out_path and os.path.exists(out_path):
                        with open(out_path, "r", encoding="utf-8", errors="replace") as f_obj: stdout = f_obj.read()[-2000:]
                    if err_path and os.path.exists(err_path):
                        with open(err_path, "r", encoding="utf-8", errors="replace") as f_obj: stderr = f_obj.read()[-2000:]
                    
                    msg = f"[System Event] Background Task [{tid}] ('{task['command']}') finished (Code {poll}).\nSTDOUT:\n{stdout.strip()}\nSTDERR:\n{stderr.strip()}\nPlease review this output and proceed with your task."
                    
                    await broadcast_message({"event": "system", "agent_id": "main", "message": f"Task {tid} finished, waking up Agent..."})
                    asyncio.create_task(handle_request_async(msg))
        except Exception as e:
            print(f"Watcher error: {e}")

async def udp_discovery_server():
    import socket
    loop = asyncio.get_running_loop()
    state.STATE_CALLBACK = lambda msg: sync_broadcast({"event": "state", "agent_id": "main", "status": msg}, loop)
    state.EVENT_CALLBACK = lambda payload: sync_broadcast(payload, loop)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception:
        pass
        
    sock.bind(("0.0.0.0", 9998))
    sock.setblocking(False)
    
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

active_connections = []

async def broadcast_message(payload):
    message = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else str(payload)
    dead = []
    for connection in list(active_connections):
        try:
            await connection.send_text(message)
        except Exception:
            dead.append(connection)
    for d in dead:
        if d in active_connections:
            active_connections.remove(d)

def sync_broadcast(payload, loop: asyncio.AbstractEventLoop):
    asyncio.run_coroutine_threadsafe(broadcast_message(payload), loop)

# State variables
chat_history = []
current_session_title = "Untitled Session"
current_session_id = None

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

def run_agent_loop_sync(command: str, history_str: str, loop: asyncio.AbstractEventLoop, image_base64: str = None, initial_loop_history=None) -> str:
    ctx = {"text": "", "state": "Thinking"}
    
    def stream_callback(token):
        ctx["text"] += token
        
        # Simply broadcast raw tokens to the frontend
        sync_broadcast({"event": "token", "agent_id": "main", "data": token}, loop)
        sys.stdout.write(token)
        sys.stdout.flush()
        
        # Update socket state
        new_state = ctx["state"]
        text_lower = ctx["text"].lower()
        if ("<thought>" in text_lower or "<|channel>thought" in text_lower) and ("</thought>" not in text_lower and "</channel>" not in text_lower):
            new_state = "Thinking"
        elif ("<scratchpad>" in text_lower and "</scratchpad>" not in text_lower):
            new_state = "Planning"
        elif "[code generated]" in text_lower or "```" in text_lower:
            new_state = "Code Generating"
            
        if new_state != ctx["state"]:
            ctx["state"] = new_state
            sync_broadcast({"event": "state", "agent_id": "main", "status": new_state}, loop)
            
    sync_broadcast({"event": "state", "agent_id": "main", "status": "Thinking"}, loop)
    if initial_loop_history:
        print(f"{Fore.GREEN}[Syntiox CORE] Resuming Agent Loop for task: '{command}'{Style.RESET_ALL}")
    else:
        print(f"{Fore.GREEN}[Syntiox CORE] Starting Agent Loop for task: '{command}'{Style.RESET_ALL}")
    
    loop_history = initial_loop_history or []
    max_steps = 30
    
    if initial_loop_history and len(initial_loop_history) > 0:
        current_step = initial_loop_history[-1].get("step", 0) + 1
    else:
        current_step = 1
        
    consecutive_recoveries = 0
    
    while current_step <= max_steps:
        if getattr(state, "STOP_REQUESTED", False):
            interaction_manager.cancel_all()
            sync_broadcast({"event": "system", "agent_id": "main", "message": "Agent loop stopped by user"}, loop)
            return "Agent stopped by user."
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
        ctx["state"] = "Thinking"
        sync_broadcast({"event": "state", "agent_id": "main", "status": "Thinking"}, loop)
        print(f"{Fore.GREEN}[Syntiox CORE] Processing... (This might take a moment){Style.RESET_ALL}")
        
        kwargs = {"image_base64": image_base64}
        step_data = get_llm_module().generate_agent_step(command, loop_history, current_step, history_str, task_list_str, stream_callback=stream_callback, **kwargs)
        
        sys.stdout.write(f"{Style.RESET_ALL}\n")
        sys.stdout.flush()
        
        if "error" in step_data:
            return "Task failed due to error: " + step_data["error"]
            
        thought = step_data.get("thought", "")
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
        
        if not step_data.get("thought") and not tool_calls and status == "CONTINUE":
            return "Task failed: Agent returned an empty or invalid response."
            
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
                    
            elif (("<thought>" in final_msg.lower() or "<scratchpad>" in final_msg.lower()) 
                and not re.search(r"<task_complete\s*/>", final_msg, re.IGNORECASE)):
                
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
            
            for tool in tool_calls:
                tool_name = tool["function"]["name"]
                tool_args = tool["function"]["arguments"]
                
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
                        all_execution_results.append(f"[Tool: {tool_name} Result]:\n{single_result}")
                        sync_broadcast({"event": "tool_result", "agent_id": "main", "tool": tool_name, "output": single_result}, loop)
                        if RICH_AVAILABLE:
                            rc.print(f"\n[bold red]DENIED - {tool_name}[/bold red]")
                        else:
                            print(f"\n{Fore.RED}[DENIED - {tool_name}]{Style.RESET_ALL}")
                        continue
                
                if tool_name not in ["system_recovery", "system_continue"]:
                    sync_broadcast({"event": "state", "agent_id": "main", "status": f"Running {tool_name}"}, loop)
                    sync_broadcast({"event": "tool_call", "agent_id": "main", "tool": tool_name, "args": tool_args}, loop)
                
                import time
                time.sleep(0.15)
                
                if tool_name in ["system_recovery", "system_continue"]:
                    single_result = execution_result
                else:
                    single_result = execute_tool(tool_name, tool_args)
                    consecutive_recoveries = 0
                
                ui_tool_name = tool_name
                ui_result = str(single_result)
                m = re.search(r'\[ACTION_START\] Tool: (.*?)\n', ui_result)
                if m:
                    ui_tool_name = m.group(1).strip()
                ui_result = ui_result.replace(f"[ACTION_START] Tool: {ui_tool_name}\n", "")
                ui_result = re.sub(r'\[ACTION_CMD\].*?\n', '', ui_result)
                ui_result = ui_result.replace("[ACTION_END]", "").strip()

                if tool_name not in ["system_recovery", "system_continue"]:
                    sync_broadcast({"event": "tool_result", "agent_id": "main", "tool": ui_tool_name, "output": ui_result}, loop)
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

        loop_history.append({
            "step": current_step,
            "thought": thought,
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
            return msg
            
        current_step += 1
        
    save_agent_loop_log(loop_history, command)
    return "Task could not be completed within the step limit."


async def handle_request_async(command: str):
    global chat_history, current_session_title, current_session_id
    loop = asyncio.get_running_loop()
    state.STATE_CALLBACK = lambda msg: sync_broadcast({"event": "state", "agent_id": "main", "status": msg}, loop)
    state.EVENT_CALLBACK = lambda payload: sync_broadcast(payload, loop)
    
    state.STOP_REQUESTED = False
    
    cmd_lower = command.strip().lower()
    
    if cmd_lower == "/history":
        return list_history()
        
    if cmd_lower.startswith("/load "):
        if current_session_id:
            archive_scratch_files(current_session_id)
        session_id_str = cmd_lower.split("/load ")[1].strip()
        try:
            session_id_int = int(session_id_str)
        except ValueError:
            return "Invalid session ID. Please use a numeric ID."
        history, msg = load_session(session_id_str)
        if history is not None:
            chat_history = history
            current_session_id = session_id_int
            current_session_title = f"Loaded Session {session_id_str}"
        return msg
        
    if cmd_lower == "/new":
        if current_session_id:
            archive_scratch_files(current_session_id)
        chat_history = []
        current_session_title = "Untitled Session"
        current_session_id = None
        try:
            from backend.session_manager import set_active_brain_path
            set_active_brain_path(None)
        except Exception:
            pass
        return "All previous conversation history and tasks have been safely archived to the history folder! We are starting fresh."
        
    if not chat_history:
        current_session_title = await asyncio.to_thread(get_llm_module().generate_session_title, command)
        current_session_id = create_new_session_folder(current_session_title)
        
    chat_history.append(f"User: {command}")
    save_chat_history(current_session_id, chat_history)
    history_str = "\n".join(chat_history)
    
    img_b64 = extract_image_base64(command)
    final_message = await asyncio.to_thread(run_agent_loop_sync, command, history_str, loop, img_b64, None)
    chat_history.append(f"Syntiox CORE: {final_message}")
    chat_history = await asyncio.to_thread(get_llm_module().summarize_memory, chat_history)
    save_chat_history(current_session_id, chat_history)
    return final_message


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
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = {"command": data}
            
            # Handle interaction responses (approvals / question answers)
            if payload.get("action") == "interaction_response":
                iid = payload.get("interaction_id", "")
                interaction_manager.resolve_interaction(iid, payload)
                continue

            if payload.get("action") == "get_workspace":
                await websocket.send_text(json.dumps({"event": "workspace_changed", **state.get_workspace_info()}, ensure_ascii=False))
                continue

            if payload.get("action") == "set_workspace":
                ws_path = payload.get("path") if "path" in payload else payload.get("workspace")
                ok, result_msg = state.set_workspace_dir(ws_path)
                if ok:
                    await broadcast_message({"event": "workspace_changed", **state.get_workspace_info()})
                else:
                    await websocket.send_text(json.dumps({
                        "event": "system",
                        "agent_id": "main",
                        "message": result_msg,
                    }, ensure_ascii=False))
                    await websocket.send_text(json.dumps({"event": "workspace_changed", **state.get_workspace_info()}, ensure_ascii=False))
                continue

            if "workspace" in payload:
                ws_val = payload.get("workspace")
                if ws_val != state.WORKSPACE_DIR:
                    ok, _ = state.set_workspace_dir(ws_val)
                    if ok:
                        await broadcast_message({"event": "workspace_changed", **state.get_workspace_info()})
            
            command = payload.get("command", "")
            response = await handle_request_async(command)
            try:
                await websocket.send_text(json.dumps({
                    "event": "final",
                    "agent_id": "main",
                    "content": response
                }, ensure_ascii=False))
            except RuntimeError:
                pass
    except Exception:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        if len(active_connections) == 0:
            state.STOP_REQUESTED = True

@app.get("/stop")
def stop_generation():
    state.STOP_REQUESTED = True
    interaction_manager.cancel_all()
    return {"status": "stopping"}

@app.get("/ping")
def ping_server(request: Request):
    client_ip = request.client.host
    print(f"[{client_ip}] Network Discovery Ping Received!")
    return {"status": "SYNTIOX_CORE_HERE"}
