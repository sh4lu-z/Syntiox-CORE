import os
import sys
import json
import asyncio
import base64
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from colorama import init, Fore, Style

# Fix Windows console emoji/unicode crash
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.text import Text
    rc = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

init(autoreset=True)

from backend import state

from backend.cloud_llm import generate_agent_step, classify_intent, generate_chat_response, generate_session_title, summarize_memory

from backend.executor import analyze_tool_call, execute_tool
from backend.session_manager import archive_workspace_files, list_history, load_session, create_new_session_folder, save_chat_history


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
            except:
                pass
    return None

# Automatically clean up workspace on server startup
try:
    if os.path.exists("workspace/walkthrough.md"):
        os.remove("workspace/walkthrough.md")
    if os.path.exists("workspace/task.md"):
        os.remove("workspace/task.md")
except Exception:
    pass

app = FastAPI(title="Syntiox CORE V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from TOOLS.os_utils import BACKGROUND_TASKS

@app.on_event("startup")
async def startup_watcher():
    asyncio.create_task(task_watcher_loop())

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
                    
                    await broadcast_message(f"\n[System Event: Task {tid} finished, waking up Agent...]\n")
                    asyncio.create_task(handle_request_async(msg))
        except Exception as e:
            print(f"Watcher error: {e}")
active_connections = []

async def broadcast_message(content: str):
    for connection in active_connections:
        try:
            await connection.send_text(content)
        except Exception:
            pass

def sync_broadcast(content: str, loop: asyncio.AbstractEventLoop):
    asyncio.run_coroutine_threadsafe(broadcast_message(content), loop)

# State variables
chat_history = []
current_session_title = "Untitled Session"
current_session_id = None
pending_code = None
pending_code_type = None
pending_loop_history = []

def run_agent_loop_sync(command: str, history_str: str, loop: asyncio.AbstractEventLoop, image_base64: str = None, initial_loop_history=None) -> str:
    ctx = {"text": "", "state": "Thinking", "buffer": ""}
    
    tags = {
        "<thought>": "\n[THINKING]\n",
        "</thought>": "\n",
        "<SCRATCHPAD>": "\n[PLAN]\n",
        "</SCRATCHPAD>": "\n",
        "<scratchpad>": "\n[PLAN]\n",
        "</scratchpad>": "\n",
        "<tool_call>": "\n[TOOL_CALL]\n",
        "</tool_call>": "\n",
        "[NEXT_STEP_REQUIRED]": "\n[NEXT_STEP_REQUIRED]\n",
        "[TASK_COMPLETE]": "\n[TASK_COMPLETE]\n",
        "```python": "\n```python\n",
        "```powershell": "\n```powershell\n"
    }
    
    print_tags = {
        "<thought>": f"\n{Fore.YELLOW}━━━ THINKING ━━━━━━━━━━━━━━━━━━━\n{Style.RESET_ALL}",
        "</thought>": f"\n{Fore.YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}\n",
        "<SCRATCHPAD>": f"\n{Fore.LIGHTBLACK_EX}━━━ PLAN ━━━━━━━━━━━━━━━━━━━━━━━\n{Style.RESET_ALL}",
        "</SCRATCHPAD>": f"\n{Fore.LIGHTBLACK_EX}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}\n",
        "<scratchpad>": f"\n{Fore.LIGHTBLACK_EX}━━━ PLAN ━━━━━━━━━━━━━━━━━━━━━━━\n{Style.RESET_ALL}",
        "</scratchpad>": f"\n{Fore.LIGHTBLACK_EX}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}\n",
        "<tool_call>": f"\n{Fore.CYAN}━━━ TOOL CALL ━━━━━━━━━━━━━━━━━━\n{Style.RESET_ALL}",
        "</tool_call>": f"\n{Fore.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Style.RESET_ALL}\n",
        "[NEXT_STEP_REQUIRED]": f"\n{Fore.MAGENTA}[NEXT_STEP_REQUIRED]{Style.RESET_ALL}\n",
        "[TASK_COMPLETE]": f"\n{Fore.GREEN}[TASK_COMPLETE]{Style.RESET_ALL}\n",
        "```python": f"\n{Fore.CYAN}```python\n",
        "```powershell": f"\n{Fore.CYAN}```powershell\n"
    }

    def stream_callback(token):
        ctx["text"] += token
        ctx["buffer"] += token
        
        while len(ctx["buffer"]) > 0:
            matched = False
            for tag, replacement in tags.items():
                if ctx["buffer"].startswith(tag):
                    if tag not in ["<thought>", "</thought>", "<SCRATCHPAD>", "</SCRATCHPAD>", "<scratchpad>", "</scratchpad>", "<tool_call>", "</tool_call>"]:
                        sync_broadcast(replacement, loop)
                    sys.stdout.write(print_tags[tag])
                    ctx["buffer"] = ctx["buffer"][len(tag):]
                    matched = True
                    break
            
            if matched:
                continue
                
            is_partial_prefix = False
            for tag in tags:
                if tag.startswith(ctx["buffer"]):
                    is_partial_prefix = True
                    break
                    
            if is_partial_prefix:
                break # Wait for more tokens
                
            char_to_print = ctx["buffer"][0]
            
            text_so_far = ctx["text"]
            in_thought = False
            if ("<thought>" in text_so_far and "</thought>" not in text_so_far):
                in_thought = True
            if ("<SCRATCHPAD>" in text_so_far and "</SCRATCHPAD>" not in text_so_far) or ("<scratchpad>" in text_so_far and "</scratchpad>" not in text_so_far):
                in_thought = True
            if ("<tool_call>" in text_so_far and "</tool_call>" not in text_so_far):
                in_thought = True
                
            if not in_thought:
                sync_broadcast(char_to_print, loop)
                
            sys.stdout.write(char_to_print)
            ctx["buffer"] = ctx["buffer"][1:]
            
        sys.stdout.flush()
        
        # Update socket state
        new_state = ctx["state"]
        if ("<thought>" in ctx["text"] or "<|channel>thought" in ctx["text"]) and ("</thought>" not in ctx["text"] and "</channel>" not in ctx["text"]):
            new_state = "Thinking"
        elif "<SCRATCHPAD>" in ctx["text"] and "</SCRATCHPAD>" not in ctx["text"]:
            new_state = "Planning"
        elif "[CODE GENERATED]" in ctx["text"] or "[POWERSHELL]" in ctx["text"] or "```python" in ctx["text"]:
            new_state = "Code Generating"
            
        if new_state != ctx["state"]:
            ctx["state"] = new_state
            sync_broadcast(f"[STATE:{new_state}]", loop)
            
    sync_broadcast("[STATE:Thinking]", loop)
    print(f"{Fore.GREEN}[Syntiox CORE] Starting Agent Loop for task: '{command}'{Style.RESET_ALL}")
    
    loop_history = initial_loop_history or []
    max_steps = 30
    current_step = 1
    
    while current_step <= max_steps:
        if getattr(state, "STOP_REQUESTED", False):
            sync_broadcast("\n\n[System: Agent loop stopped by user]\n", loop)
            return "Agent stopped by user."
        print(f"{Fore.GREEN}[Syntiox CORE] --- Agent Loop Step {current_step} ---{Style.RESET_ALL}")
        task_list_str = ""
        task_file_path = os.path.join("workspace", "task.md")
        if os.path.exists(task_file_path):
            try:
                with open(task_file_path, "r", encoding="utf-8") as f:
                    task_list_str = f.read()
            except:
                pass
        
        ctx["text"] = "" 
        ctx["buffer"] = ""
        ctx["state"] = "Thinking"
        sync_broadcast("[STATE:Thinking]", loop)
        print(f"{Fore.GREEN}[Syntiox CORE] Processing... (This might take a moment){Style.RESET_ALL}")
        
        kwargs = {"image_base64": image_base64} if getattr(state, "LLM_PROVIDER", "local") == "google" else {}
        step_data = generate_agent_step(command, loop_history, current_step, history_str, task_list_str, stream_callback=stream_callback, **kwargs)
        
        if ctx["buffer"]:
            sync_broadcast(ctx["buffer"], loop)
            sys.stdout.write(ctx["buffer"])
            ctx["buffer"] = ""
        sync_broadcast("\n", loop)
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
                    from rich.table import Table
                    # Remove the truncation, show the full content beautifully
                    # Use a rich panel to render the tool execution cleanly
                    console_text = f"[bold cyan]EXECUTING TOOL:[/bold cyan] [bold white]{t_name}[/bold white]\n"
                    rc.print(Panel(console_text, border_style="cyan", padding=(0, 1)))
                    for k, v in t_args.items():
                        val_str = str(v)
                        rc.print(f"[bold cyan]{k.upper()}:[/bold cyan]")
                        if k in ["command", "content", "code", "file_content", "code_content", "replacementContent"]:
                            # Assume html or python for rich syntax guessing, fallback to text
                            syntax = Syntax(val_str, "html" if "<html" in val_str else "python", theme="monokai", word_wrap=True)
                            rc.print(Panel(syntax, border_style="blue", padding=(0, 1)))
                        else:
                            rc.print(f"[white]{val_str}[/white]")
                    print("\n")
                else:
                    print(f"\n{Fore.LIGHTCYAN_EX}╭──────────────────────────────────────────────────────────────────────────")
                    print(f"│ {Fore.CYAN}EXECUTING TOOL: {Fore.WHITE}{t_name}")
                    print(f"{Fore.LIGHTCYAN_EX}├──────────────────────────────────────────────────────────────────────────{Style.RESET_ALL}")
                    
                    for k, v in t_args.items():
                        val_str = str(v)
                        print(f"{Fore.CYAN}│ {k.upper()}: {Fore.WHITE}{val_str}{Style.RESET_ALL}")
                    print(f"{Fore.LIGHTCYAN_EX}╰──────────────────────────────────────────────────────────────────────────{Style.RESET_ALL}\n")
        
        if not step_data.get("thought") and not tool_calls and status == "CONTINUE":
            return "Task failed: Agent returned an empty or invalid response."
            
        execution_result = ""
        
        if not tool_calls and status == "COMPLETE":
            final_msg = step_data.get("final_message", "")
            
            # Universal Protocol: If it didn't explicitly say it's done/waiting, AND it was thinking, it dropped the tool.
            if "[NEXT_STEP_REQUIRED]" in final_msg or (("<thought>" in final_msg or "<SCRATCHPAD>" in final_msg) and "[TASK_COMPLETE]" not in final_msg):
                # The model was thinking but dropped the tool call payload! Force it to continue.
                sync_broadcast("\n[STATE:Recovering from missing tool call...]\n", loop)
                print(f"{Fore.YELLOW}[Syntiox CORE] Model dropped tool call payload or API injected NEXT_STEP_REQUIRED. Forcing continuation...{Style.RESET_ALL}")
                
                tool_calls = [{"function": {"name": "system_recovery", "arguments": {}}}]
                execution_result = "System Warning: A tool call was expected but not found, or the previous response was malformed. Please output your tool call NOW using valid JSON/XML. If you are completely finished, output your final response to the user and ensure you append [TASK_COMPLETE] at the end."
                status = "CONTINUE"
            else:
                pass # Proceed to cleanup at the bottom of the loop
        
        if tool_calls:
            from backend.executor import analyze_tool_call, execute_tool
            import json
            import re
            
            all_execution_results = []
            
            for tool in tool_calls:
                tool_name = tool["function"]["name"]
                tool_args = tool["function"]["arguments"]
                
                requires_approval = analyze_tool_call(tool_name, tool_args)
                if requires_approval:
                    global pending_code, pending_code_type
                    pending_code = json.dumps(tool_args, indent=2)
                    pending_code_type = tool_name
                    pending_loop_history = loop_history.copy()
                    return f"⚠️ **Dangerous command detected!** Do you want me to execute tool '{tool_name}' with args:\n```json\n{pending_code}\n```\nType 'Yes' to approve or 'No' to cancel."
                
                # --- UI State Beautification ---
                friendly_states = {
                    "write_to_file": "Writing new code",
                    "replace_file_content": "Modifying code",
                    "multi_replace_file_content": "Modifying code",
                    "run_terminal_command": "Executing command",
                    "grep_search": "Searching files",
                    "semantic_search_codebase": "Running AI search",
                    "view_file": "Reading file",
                    "run_mcp_tool": "Connecting to MCP",
                    "call_mcp_tool": "Connecting to MCP",
                    "goto": "Browsing the web",
                    "click": "Interacting with page",
                    "extract": "Reading webpage",
                    "search_web": "Searching the web"
                }
                ui_state_msg = friendly_states.get(tool_name, f"Running {tool_name}")
                sync_broadcast(f"[STATE:{ui_state_msg}]", loop)
                import time
                time.sleep(1) # UI visual delay & LLM API Rate Limit buffer
                
                print(f"{Fore.MAGENTA}[Syntiox CORE] Executing tool {tool_name}...{Style.RESET_ALL}")
                
                if tool_name == "system_recovery":
                    single_result = execution_result
                else:
                    single_result = execute_tool(tool_name, tool_args)
                
                ui_tool_name = tool_name
                ui_result = str(single_result)
                m = re.search(r'\[ACTION_START\] Tool: (.*?)\n', ui_result)
                if m:
                    ui_tool_name = m.group(1).strip()
                ui_result = ui_result.replace(f"[ACTION_START] Tool: {ui_tool_name}\n", "")
                ui_result = re.sub(r'\[ACTION_CMD\].*?\n', '', ui_result)
                ui_result = ui_result.replace("[ACTION_END]", "").strip()

                sync_broadcast(f"\n[TOOL_UI:{ui_tool_name}]\n", loop)
                if RICH_AVAILABLE:
                    rc.print(Panel(str(single_result), title=f"[magenta]EXECUTION RESULT - {tool_name}[/magenta]", border_style="magenta", padding=(1, 2)))
                else:
                    print(f"{Fore.MAGENTA}[EXECUTION RESULT - {tool_name}]\n{single_result}{Style.RESET_ALL}")
                
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
            msg = step_data.get("final_message", "Task fully completed successfully.")
            
            import re
            # Clean up XML tags from final message
            msg = re.sub(r'<thought>.*?</thought>', '', msg, flags=re.DOTALL | re.IGNORECASE)
            msg = re.sub(r'<SCRATCHPAD>.*?</SCRATCHPAD>', '', msg, flags=re.DOTALL | re.IGNORECASE)
            msg = msg.replace("[TASK_COMPLETE]", "").strip()
            if not msg:
                msg = "Task completed successfully."
            
            # We no longer append HTML accordions because the UI handles it natively during streaming.
            
            return msg
            
        current_step += 1
        
    return "Task could not be completed within the step limit."


def run_chat_sync(command: str, history_str: str, loop: asyncio.AbstractEventLoop, image_base64: str = None) -> str:
    def stream_callback(token):
        sync_broadcast(token, loop)
        sys.stdout.write(token)
        sys.stdout.flush()
        
    print(f"{Fore.GREEN}[Syntiox CORE] Generating chat response...{Style.RESET_ALL}")
    sync_broadcast("[STATE:Typing]", loop)
    kwargs = {"image_base64": image_base64} if getattr(state, "LLM_PROVIDER", "local") == "google" else {}
    response = generate_chat_response(command, history_str, stream_callback=stream_callback, **kwargs)
    sync_broadcast("\n", loop)
    sys.stdout.write("\n")
    return response

async def handle_request_async(command: str):
    global chat_history, current_session_title, current_session_id, pending_code, pending_code_type, pending_loop_history
    loop = asyncio.get_running_loop()
    
    # Reset stop request for the new task
    state.STOP_REQUESTED = False
    
    cmd_lower = command.strip().lower()
    
    if pending_code is not None:
        if cmd_lower in ['yes', 'y']:
            import json
            try:
                args_dict = json.loads(pending_code)
            except:
                args_dict = {}
            execution_result = await asyncio.to_thread(execute_tool, pending_code_type, args_dict)
            pending_code = None
            pending_code_type = None
            chat_history.append(f"User: [Approved and executed previous code]")
            chat_history = summarize_memory(chat_history)
            save_chat_history(current_session_id, chat_history)
            history_str = "\n".join(chat_history)
            final_message = await asyncio.to_thread(run_agent_loop_sync, f"The code was approved and executed. Here is the result:\n{execution_result}\nContinue with the next step.", history_str, loop, None, pending_loop_history)
            pending_loop_history = []
            chat_history.append(f"Syntiox CORE: {final_message}")
            return final_message
        elif cmd_lower in ['no', 'n']:
            pending_code = None
            pending_code_type = None
            chat_history.append(f"User: [Rejected previous code]")
            chat_history = summarize_memory(chat_history)
            save_chat_history(current_session_id, chat_history)
            history_str = "\n".join(chat_history)
            final_message = await asyncio.to_thread(run_agent_loop_sync, "I rejected the execution of that code for safety. You must find another way.", history_str, loop, None, pending_loop_history)
            pending_loop_history = []
            chat_history.append(f"Syntiox CORE: {final_message}")
            return final_message
        else:
            return "Please answer 'Yes' or 'No' to approve or cancel the dangerous command."
            
    if cmd_lower == "/history":
        return list_history()
        
    if cmd_lower.startswith("/load "):
        if current_session_id:
            archive_workspace_files(current_session_id)
        session_id_str = cmd_lower.split("/load ")[1].strip()
        history, msg = load_session(session_id_str)
        if history is not None:
            chat_history = history
            current_session_id = int(session_id_str)
            current_session_title = f"Loaded Session {session_id_str}"
        return msg
        
    if cmd_lower == "/new":
        if current_session_id:
            archive_workspace_files(current_session_id)
        chat_history = []
        current_session_title = "Untitled Session"
        current_session_id = None
        try:
            if os.path.exists("workspace/walkthrough.md"):
                os.remove("workspace/walkthrough.md")
            if os.path.exists("workspace/task.md"):
                os.remove("workspace/task.md")
        except Exception:
            pass
        return "All previous conversation history and tasks have been safely archived to the history folder! We are starting fresh. 🚀"
        
    if not chat_history:
        current_session_title = generate_session_title(command)
        current_session_id = create_new_session_folder(current_session_title)
        
    chat_history.append(f"User: {command}")
    chat_history = summarize_memory(chat_history)
    save_chat_history(current_session_id, chat_history)
    history_str = "\n".join(chat_history)
    
    # Check if a manual mode override was passed
    manual_mode = getattr(state, "manual_mode", None)
    
    intent = classify_intent(command, manual_override=manual_mode, history_str=history_str)
    img_b64 = extract_image_base64(command)
    
    # Inject UI-specific instructions
    ui_mode = os.getenv("LAUNCH_UI", "terminal")
    if ui_mode == "web":
        ui_instruction = "\n\n[SYSTEM INSTRUCTION: The user is using a modern rich Web UI. Always format your responses beautifully using rich Markdown, including headers, tables, bold text, and code blocks. If there are mathematical equations, format them strictly in LaTeX for MathJax rendering.]"
    else:
        ui_instruction = "\n\n[SYSTEM INSTRUCTION: The user is using a plain Terminal CLI. Strictly avoid using complex markdown tables, LaTeX math, or heavy formatting. Use simple plain text, bullet points, and basic spacing so it renders cleanly in a standard terminal shell.]"
    
    command_with_context = command + ui_instruction
    
    if intent == "CHAT":
        kwargs = {"image_base64": img_b64} if getattr(state, "LLM_PROVIDER", "local") == "google" else {}
        response = await asyncio.to_thread(run_chat_sync, command_with_context, history_str, loop, **kwargs)
        chat_history.append(f"Syntiox CORE: {response}")
        chat_history = summarize_memory(chat_history)
        save_chat_history(current_session_id, chat_history)
        return response
    else:
        final_message = await asyncio.to_thread(run_agent_loop_sync, command_with_context, history_str, loop, img_b64)
        chat_history.append(f"Syntiox CORE: {final_message}")
        chat_history = summarize_memory(chat_history)
        save_chat_history(current_session_id, chat_history)
        return final_message


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            
            # Check if JSON payload (for Mode toggle support)
            try:
                payload = json.loads(data)
                command = payload.get("command", "")
                mode = payload.get("mode", "auto")
                
                # Store the manual mode temporarily in state
                if mode != "auto":
                    setattr(state, "manual_mode", mode)
                else:
                    if hasattr(state, "manual_mode"):
                        delattr(state, "manual_mode")
            except json.JSONDecodeError:
                command = data
                if hasattr(state, "manual_mode"):
                    delattr(state, "manual_mode")
            
            response = await handle_request_async(command)
            try:
                await websocket.send_text(f"[__SYNTIOX_FINAL__]{response}[__SYNTIOX_DONE__]")
            except RuntimeError:
                # WebSocket was closed before we could send (e.g. user pressed Stop)
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
    return {"status": "stopping"}

