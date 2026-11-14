import codecs
import subprocess
import os
import threading
import uuid
import time
from typing import Dict, Any
from tools.logger import action_logger

# Global registry for background tasks
BACKGROUND_TASKS: Dict[str, Dict[str, Any]] = {}

@action_logger("run_background_command")
def run_background_command(command: str, cwd: str = None) -> str:
    """Explicit tool to run a long-running process like a web server, development server (e.g., node, python -m http.server), or any command that does not exit immediately in the background. 
    Never use `run_terminal_command` for servers, as it will block execution and crash the agent loop. 
    You can manage spawned background tasks using the `manage_task` tool (actions: 'list', 'status', 'kill', 'send_input').
    IMPORTANT: You MUST always provide an absolute path for the 'cwd' parameter (e.g., C:\\Users\\...\\project). Do NOT use relative paths."""
    # Clean up file handles for tasks that already exited
    for tid in list(BACKGROUND_TASKS.keys()):
        task = BACKGROUND_TASKS[tid]
        if task["process"].poll() is not None and "files" in task:
            for f_obj in task["files"]:
                try:
                    f_obj.close()
                except Exception:
                    pass
            del task["files"]
    return run_terminal_command(command, cwd=cwd, is_background=True)

@action_logger("run_terminal_command")
def run_terminal_command(command: str, cwd: str = None, timeout: int = 60, is_background: bool = False) -> str:
    """Runs a shell command. Use run_background_command for long-running servers or infinite loops to avoid blocking execution. IMPORTANT: You MUST always provide an absolute path for the 'cwd' parameter. Do NOT use relative paths."""
    try:
        cmd_lower = command.lower()
        if ".sh4lu-z" in cmd_lower:
            destructive_ops = ["rm ", "rmdir", "del ", "rd ", "remove-item", "erase"]
            if any(op in cmd_lower for op in destructive_ops):
                return "Error: Security Policy Violation: You are strictly forbidden from deleting or modifying Syntiox CORE system files (.sh4lu-z) via terminal commands."

        if not cwd:
            from backend import state
            full_cwd = os.path.abspath(state.get_workspace_dir())
        elif os.path.isabs(cwd):
            full_cwd = os.path.abspath(cwd)
        else:
            from backend import state
            full_cwd = os.path.abspath(os.path.join(state.get_workspace_dir(), cwd))
        os.makedirs(full_cwd, exist_ok=True)
        
        if is_background:
            task_id = f"task-{str(uuid.uuid4())[:8]}"
            
            out_file_path = os.path.join(full_cwd, f"{task_id}.out")
            err_file_path = os.path.join(full_cwd, f"{task_id}.err")
            out_file = open(out_file_path, "w", encoding="utf-8")
            err_file = open(err_file_path, "w", encoding="utf-8")
            
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            # Add Syntiox CORE root to PYTHONPATH so agents can import internal modules
            env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

            process = subprocess.Popen(
                command,
                shell=True,
                stdout=out_file,
                stderr=err_file,
                stdin=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=full_cwd,
                env=env
            )
            
            BACKGROUND_TASKS[task_id] = {
                "process": process,
                "command": command,
                "status": "Running",
                "start_time": time.time(),
                "cwd": full_cwd,
                "files": (out_file, err_file),
                "paths": (out_file_path, err_file_path)
            }
            
            return f"Success: Command started in background. Task ID: {task_id}. Use 'manage_task' to check status, kill, or send input."

        # Synchronous execution
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        # Add Syntiox CORE root to PYTHONPATH so agents can import internal modules
        env["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        from backend import state, event_bus

        call_id, _ = event_bus.current_tool()
        agent_id = event_bus.current_agent()

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            cwd=full_cwd,
            env=env,
        )

        stdout_chunks = []
        stderr_chunks = []

        def _pump(pipe, stream_name: str, chunks: list):
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            fd = pipe.fileno()
            buf = []
            buf_len = 0
            last_flush = 0.0

            def flush():
                nonlocal buf_len, last_flush
                if not buf:
                    return
                text = "".join(buf)
                buf.clear()
                buf_len = 0
                last_flush = time.monotonic()
                payload = {
                    "event": "tool_output",
                    "agent_id": agent_id,
                    "stream": stream_name,
                    "data": text.replace("\r\n", "\n"),
                }
                if call_id:
                    payload["call_id"] = call_id
                state.emit_event(payload)

            try:
                while True:
                    raw = os.read(fd, 4096)
                    if not raw:
                        tail = decoder.decode(b"", final=True)
                        if tail:
                            chunks.append(tail)
                            buf.append(tail)
                        flush()
                        break
                    chunk = decoder.decode(raw, final=False)
                    if chunk:
                        chunks.append(chunk)
                        buf.append(chunk)
                        buf_len += len(chunk)
                        if buf_len >= 4096 or (time.monotonic() - last_flush) >= 0.1:
                            flush()
            except OSError:
                flush()

        t_out = threading.Thread(target=_pump, args=(process.stdout, "stdout", stdout_chunks), daemon=True)
        t_err = threading.Thread(target=_pump, args=(process.stderr, "stderr", stderr_chunks), daemon=True)
        t_out.start()
        t_err.start()

        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )
                except Exception:
                    pass
            try:
                process.kill()
            except Exception:
                pass
            return f"Error: Command timed out after {timeout} seconds."
        finally:
            t_out.join(timeout=2)
            t_err.join(timeout=2)
            for pipe in (process.stdout, process.stderr):
                if pipe:
                    try:
                        pipe.close()
                    except Exception:
                        pass

        output = "".join(stdout_chunks).replace("\r\n", "\n").strip()
        error = "".join(stderr_chunks).replace("\r\n", "\n").strip()

        if returncode == 0:
            if output:
                return f"Success:\n{output}"
            return "Success (No output)"
        return f"Command Failed (Code {returncode}):\nSTDOUT: {output}\nSTDERR: {error}"

    except Exception as e:
        return f"Error running command: {str(e)}"

@action_logger("manage_task")
def manage_task(action: str, task_id: str = None, input_text: str = None) -> str:
    """Manage background tasks. Actions: 'list', 'status', 'kill', 'send_input'"""
    if action == "list":
        if not BACKGROUND_TASKS:
            return "No background tasks currently running."
        
        result = "Background Tasks:\n"
        for tid, task in list(BACKGROUND_TASKS.items()):
            p = task["process"]
            poll = p.poll()
            status = "Running" if poll is None else f"Exited (Code {poll})"
            task["status"] = status
            result += f"- [{tid}] {status}: '{task['command']}' (Uptime: {int(time.time() - task['start_time'])}s)\n"
            
            if poll is not None and "files" in task:
                for f_obj in task["files"]:
                    try: f_obj.close()
                    except Exception: pass
                del task["files"]
                
        return result
        
    if not task_id or task_id not in BACKGROUND_TASKS:
        return f"Error: Task ID '{task_id}' not found. It may have exited or never existed."
        
    task = BACKGROUND_TASKS[task_id]
    p = task["process"]
    
    if action == "status":
        poll = p.poll()
        if poll is not None and "files" in task:
            for f_obj in task["files"]:
                try: f_obj.close()
                except Exception: pass
            del task["files"]
            
        out_path, err_path = task.get("paths", (None, None))
        stdout, stderr = "", ""
        if out_path and os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8", errors="replace") as f_obj: stdout = f_obj.read()[-2000:]
        if err_path and os.path.exists(err_path):
            with open(err_path, "r", encoding="utf-8", errors="replace") as f_obj: stderr = f_obj.read()[-2000:]
            
        if poll is not None:
            del BACKGROUND_TASKS[task_id]
            return f"Task [{task_id}] Exited with Code {poll}.\nSTDOUT:\n{stdout.strip()}\nSTDERR:\n{stderr.strip()}"
        
        return f"Task [{task_id}] is Running: '{task['command']}'\nSTDOUT (recent):\n{stdout.strip()}\nSTDERR (recent):\n{stderr.strip()}"
        
    elif action == "kill":
        import platform
        if "files" in task:
            for f_obj in task["files"]:
                try: f_obj.close()
                except Exception: pass
            del task["files"]
            
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        else:
            p.kill()
        del BACKGROUND_TASKS[task_id]
        return f"Task [{task_id}] killed successfully."
        
    elif action == "send_input":
        if not input_text:
            return "Error: input_text required for send_input."
        if p.poll() is not None:
            return f"Error: Task [{task_id}] is no longer running."
            
        try:
            p.stdin.write(input_text + "\n")
            p.stdin.flush()
            return f"Success: Input sent to task [{task_id}]."
        except Exception as e:
            return f"Error sending input: {str(e)}"
            
    return f"Error: Invalid action '{action}'. Use list, status, kill, or send_input."
