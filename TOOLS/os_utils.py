import subprocess
import os
import uuid
import time
from typing import Dict, Any
from TOOLS.logger import action_logger

# Global registry for background tasks
BACKGROUND_TASKS: Dict[str, Dict[str, Any]] = {}

@action_logger("run_background_command")
def run_background_command(command: str, cwd: str = None) -> str:
    """Explicit tool to run a long-running server or command in the background. Use this for starting servers. IMPORTANT: You MUST always provide an absolute path for the 'cwd' parameter (e.g., C:\\Users\\...\\workspace\\project). Do NOT use relative paths, as they will resolve incorrectly."""
    return run_terminal_command(command, cwd=cwd, is_background=True)

@action_logger("run_terminal_command")
def run_terminal_command(command: str, cwd: str = None, timeout: int = 60, is_background: bool = False) -> str:
    """Runs a shell command. Use run_background_command for long-running servers. IMPORTANT: You MUST always provide an absolute path for the 'cwd' parameter. Do NOT use relative paths."""
    try:
        if cwd is None:
            from backend.config_paths import WORKSPACE_DIR
            cwd = WORKSPACE_DIR
        full_cwd = os.path.abspath(cwd)
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
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=full_cwd,
            timeout=timeout,
            env=env
        )
        
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        if result.returncode == 0:
            if output:
                return f"Success:\n{output}"
            else:
                return "Success (No output)"
        else:
            return f"Command Failed (Code {result.returncode}):\nSTDOUT: {output}\nSTDERR: {error}"
            
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
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
                    except: pass
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
                except: pass
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
