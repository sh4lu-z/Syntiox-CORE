import os
import sys
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from colorama import init, Fore, Style

# Fix Windows console emoji/unicode crash
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

init(autoreset=True)

from backend.llm_client import generate_agent_step, classify_intent, generate_chat_response, generate_session_title, summarize_memory
from backend.executor import analyze_code, execute_code
from backend.session_manager import archive_workspace_files, list_history, load_session, create_new_session_folder, save_chat_history
from backend import state
import base64
import re

def extract_image_base64(text: str):
    matches = re.findall(r'["\']([a-zA-Z]:\\[^"\']+\.(?:png|jpg|jpeg|webp))["\']', text, re.IGNORECASE)
    if not matches:
        matches = re.findall(r'([a-zA-Z]:\\[\w\\\.\-\s]+\.(?:png|jpg|jpeg|webp))', text, re.IGNORECASE)
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

def run_agent_loop_sync(command: str, history_str: str, loop: asyncio.AbstractEventLoop, image_base64: str = None) -> str:
    ctx = {"text": "", "state": "Thinking", "buffer": ""}
    
    tags = {
        "<thought>": "\n[THINKING]\n",
        "</thought>": "\n",
        "<SCRATCHPAD>": "\n[PLAN]\n",
        "</SCRATCHPAD>": "\n",
        "[POWERSHELL]": "\n[POWERSHELL]\n",
        "[CODE GENERATED]": "\n[CODE GENERATED]\n",
        "[NEXT_STEP_REQUIRED]": "\n[NEXT_STEP_REQUIRED]\n",
        "[TASK_COMPLETE]": "\n[TASK_COMPLETE]\n",
        "```python": "\n```python\n",
        "```powershell": "\n```powershell\n"
    }
    
    print_tags = {
        "<thought>": f"\n{Fore.YELLOW}[THINKING]\n",
        "</thought>": f"{Style.RESET_ALL}\n",
        "<SCRATCHPAD>": f"\n{Fore.LIGHTBLACK_EX}[PLAN]\n",
        "</SCRATCHPAD>": f"{Style.RESET_ALL}\n",
        "[POWERSHELL]": f"\n{Fore.CYAN}[POWERSHELL]\n",
        "[CODE GENERATED]": f"\n{Fore.CYAN}[CODE GENERATED]\n",
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
            sync_broadcast(char_to_print, loop)
            sys.stdout.write(char_to_print)
            ctx["buffer"] = ctx["buffer"][1:]
            
        sys.stdout.flush()
        
        # Update socket state
        new_state = ctx["state"]
        if ("<thought>" in ctx["text"] or "<|channel>thought" in ctx["text"]) and ("</thought>" not in ctx["text"] and "<channel|>" not in ctx["text"]):
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
    
    scratchpad = ""
    execution_result = ""
    max_steps = 30
    current_step = 1
    
    while current_step <= max_steps:
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
        
        step_data = generate_agent_step(command, scratchpad, execution_result, image_base64, current_step, history_str, task_list_str, stream_callback=stream_callback)
        
        if ctx["buffer"]:
            sync_broadcast(ctx["buffer"], loop)
            sys.stdout.write(ctx["buffer"])
            ctx["buffer"] = ""
        sync_broadcast("\n", loop)
        sys.stdout.write(f"{Style.RESET_ALL}\n")
        sys.stdout.flush()
        
        if "error" in step_data:
            return "Task failed due to error: " + step_data["error"]
            
        scratchpad = step_data.get("scratchpad", "")
        code = step_data.get("code", "")
        code_type = step_data.get("code_type", "python")
        status = step_data.get("status", "CONTINUE")
        
        if not step_data.get("thought") and not code and status == "CONTINUE":
            return "Task failed: Agent returned an empty or invalid response."
            
        if not code and status == "COMPLETE":
            return step_data.get("final_message", "Task fully completed successfully.")
            
        if code:
            requires_approval = analyze_code(code, code_type)
            if requires_approval:
                global pending_code, pending_code_type
                pending_code = code
                pending_code_type = code_type
                return f"⚠️ **Dangerous command detected!** Do you want me to execute this?\n```\n{code}\n```\nType 'Yes' to approve or 'No' to cancel."
            
            sync_broadcast(f"[STATE:CMD Running]" if code_type == "powershell" else "[STATE:Code Running]", loop)
            print(f"{Fore.MAGENTA}[Syntiox CORE] Executing {code_type} code...{Style.RESET_ALL}")
            execution_result = execute_code(code, code_type)
            sync_broadcast(f"\n[EXECUTION RESULT]\n{execution_result}\n", loop)
            print(f"{Fore.MAGENTA}[EXECUTION RESULT]\n{execution_result}{Style.RESET_ALL}")
            
            # Reset image_base64 for the next step, unless a new image is provided
            image_base64 = None
            img_match = re.search(r'\[IMAGE_RESULT\]\s*(.+?\.(png|jpg|jpeg|webp))', execution_result, re.IGNORECASE)
            if img_match:
                img_path = img_match.group(1).strip()
                if os.path.exists(img_path):
                    try:
                        with open(img_path, "rb") as f:
                            image_base64 = base64.b64encode(f.read()).decode('utf-8')
                        print(f"{Fore.CYAN}[Syntiox CORE] Captured Visual Feedback from: {img_path}{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}[Syntiox CORE] Failed to read image result: {e}{Style.RESET_ALL}")
        else:
            execution_result = ""
                
        if status == "COMPLETE":
            print(f"{Fore.GREEN}[Syntiox CORE] Task fully completed!{Style.RESET_ALL}")
            msg = step_data.get("final_message", "Task fully completed successfully.")
            if code and execution_result:
                msg += f"\n\n[System] Execution Result:\n{execution_result}"
            return msg
            
        current_step += 1
        
    return "Task could not be completed within the step limit."


async def handle_request_async(command: str):
    global chat_history, current_session_title, current_session_id, pending_code, pending_code_type
    loop = asyncio.get_running_loop()
    
    # Reset stop request for the new task
    state.STOP_REQUESTED = False
    
    cmd_lower = command.strip().lower()
    
    if pending_code is not None:
        if cmd_lower in ['yes', 'y']:
            execution_result = await asyncio.to_thread(execute_code, pending_code, pending_code_type)
            pending_code = None
            pending_code_type = None
            chat_history.append(f"User: [Approved and executed previous code]")
            chat_history = summarize_memory(chat_history)
            save_chat_history(current_session_id, chat_history)
            history_str = "\n".join(chat_history)
            
            img_b64 = extract_image_base64(command)
            final_message = await asyncio.to_thread(run_agent_loop_sync, f"The code was approved and executed. Here is the result:\n{execution_result}\nContinue with the next step.", history_str, loop, img_b64)
            chat_history.append(f"Syntiox CORE: {final_message}")
            return final_message
        elif cmd_lower in ['no', 'n']:
            pending_code = None
            pending_code_type = None
            chat_history.append(f"User: [Rejected previous code]")
            chat_history = summarize_memory(chat_history)
            save_chat_history(current_session_id, chat_history)
            history_str = "\n".join(chat_history)
            
            img_b64 = extract_image_base64(command)
            final_message = await asyncio.to_thread(run_agent_loop_sync, "I rejected the execution of that code for safety. You must find another way.", history_str, loop, img_b64)
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
    
    intent = classify_intent(command)
    img_b64 = extract_image_base64(command)
    
    if intent == "CHAT":
        response = generate_chat_response(command, history_str, image_base64=img_b64)
        chat_history.append(f"Syntiox CORE: {response}")
        chat_history = summarize_memory(chat_history)
        save_chat_history(current_session_id, chat_history)
        return response
    else:
        final_message = await asyncio.to_thread(run_agent_loop_sync, command, history_str, loop, img_b64)
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
            response = await handle_request_async(data)
            await websocket.send_text(f"[FINAL]{response}[DONE]")
    except WebSocketDisconnect:
        active_connections.remove(websocket)

@app.get("/stop")
def stop_generation():
    state.STOP_REQUESTED = True
    return {"status": "stopping"}

