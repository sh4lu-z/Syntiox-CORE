import os
import sys

# --- MICRO-CORE ARCHITECTURE: DYNAMIC DEPENDENCY LOADING ---
is_exe = getattr(sys, 'frozen', False)
if is_exe:
    # If running as an EXE, load heavy packages from the external environment
    appdata = os.environ.get('LOCALAPPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Local'))
    ext_env_path = os.path.join(appdata, 'Syntiox_CORE', 'env', 'Lib', 'site-packages')
    if os.path.exists(ext_env_path) and ext_env_path not in sys.path:
        sys.path.insert(0, ext_env_path)
# -----------------------------------------------------------

import uvicorn
from colorama import init, Fore, Style

# Add backend to path
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

# Ensure current working directory is always the script's directory
os.chdir(base_dir)

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Initialize colorama
init(autoreset=True)

def setup_auth_token():
    import random
    
    home_dir = os.path.expanduser("~")
    config_dir = os.path.join(home_dir, ".sh4lu-z", "Syntiox CORE", "config")
    os.makedirs(config_dir, exist_ok=True)
    
    token_file = os.path.join(config_dir, "auth_token.txt")
    
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            token = f.read().strip()
    else:
        token = str(random.randint(1000, 9999))
        with open(token_file, "w") as f:
            f.write(token)
            
    os.environ["SYNTIOX_AUTH_TOKEN"] = token
    return token

if __name__ == "__main__":
    import subprocess
    import time
    import argparse
    import atexit
    import urllib.request
    import json
    
    # 1. Define is_server_running helper
    def is_server_running():
        try:
            req = urllib.request.Request("http://127.0.0.1:9999/ping")
            with urllib.request.urlopen(req, timeout=1) as response:
                data = json.loads(response.read().decode())
                if data.get("status") == "SYNTIOX_CORE_HERE":
                    return True
        except Exception:
            pass
        return False

    parser = argparse.ArgumentParser(description="Syntiox CORE Server")
    parser.add_argument("--logs", action="store_true", help="Show the backend log terminal")
    parser.add_argument("--background", action="store_true", help="Run server in the background and add to startup")
    parser.add_argument("--stop", action="store_true", help="Stop the background server and remove from startup")
    parser.add_argument("--run-frontend", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--run-backend", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    is_exe = getattr(sys, 'frozen', False)
    
    if args.run_frontend:
        # Direct execution of frontend for .exe mode
        import frontend.chat_cli
        app = frontend.chat_cli.ChatApp()
        app.run()
        sys.exit(0)
        
    if args.run_backend:
        # Direct execution of backend for .exe mode
        uvicorn.run("backend.main:app", host="0.0.0.0", port=9999, log_level="warning", access_log=False)
        sys.exit(0)

    os.system("chcp 65001 > nul")
    
    auth_token = setup_auth_token()
    
    # Define paths
    home_dir = os.path.expanduser("~")
    data_dir = os.path.join(home_dir, ".sh4lu-z", "Syntiox CORE")
    config_dir = os.path.join(data_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    log_file = os.path.join(config_dir, "server.log")
    
    # Handle --stop
    if args.stop:
        print(f"{Fore.YELLOW}Stopping background server and removing from startup...{Style.RESET_ALL}")
        # Stop process on port 9999 (Windows specific)
        import re
        try:
            output = subprocess.check_output('netstat -ano | findstr :9999', shell=True).decode()
            pids = set()
            for line in output.strip().split('\n'):
                if 'LISTENING' in line:
                    parts = line.strip().split()
                    pids.add(parts[-1])
            for pid in pids:
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Killed process {pid} on port 9999.")
        except:
            print("No server running on port 9999.")
            
        # Remove from startup
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        vbs_path = os.path.join(startup_dir, "SyntioxCORE_Background.vbs")
        if os.path.exists(vbs_path):
            os.remove(vbs_path)
            print("Removed from Windows Startup.")
        sys.exit(0)
        
    server_running = is_server_running()

    if args.background:
        if server_running:
            print(f"{Fore.YELLOW}Syntiox CORE is already running in the background.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}Starting Syntiox CORE in the background...{Style.RESET_ALL}")
            # Ensure log file exists
            with open(log_file, "a") as f:
                f.write("\n--- Starting Background Server ---\n")
                
            # Spawn detached process
            env = os.environ.copy()
            CREATE_NO_WINDOW = 0x08000000
            
            if is_exe:
                cmd = [sys.executable, "--run-backend"]
            else:
                cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9999", "--log-level", "warning"]

            subprocess.Popen(
                cmd,
                stdout=open(log_file, "a"),
                stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
                env=env
            )
            print(f"Server started. Logs redirected to {log_file}")
            
        # Install to startup
        startup_dir = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        vbs_path = os.path.join(startup_dir, "SyntioxCORE_Background.vbs")
        
        # We need a vbs that calls stx.cmd --background
        # Where is stx.cmd? Let's use the absolute path to python server.py instead to be perfectly reliable
        python_exe = sys.executable
        server_py_path = os.path.abspath(__file__)
        vbs_content = f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{python_exe}"" ""{server_py_path}"" --background", 0, False'
        
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(vbs_content)
        print(f"Added to Windows Startup: {vbs_path}")
        sys.exit(0)

    if args.logs:
        if server_running:
            print(f"{Fore.GREEN}Server is already running in the background. Tailing logs...{Style.RESET_ALL}")
            if os.path.exists(log_file):
                print(f"{Fore.CYAN}--- Live Logs from {log_file} ---{Style.RESET_ALL}")
                try:
                    # Tail logs in powershell
                    subprocess.run(["powershell", "-NoProfile", "-Command", f"Get-Content -Path '{log_file}' -Wait"])
                except KeyboardInterrupt:
                    pass
            else:
                print(f"{Fore.RED}Log file not found at {log_file}. Server might be running natively without redirection.{Style.RESET_ALL}")
            sys.exit(0)
            
        # Legacy mode: Show logs in this window, spawn CLI in a new window
        os.system("title Syntiox CORE Backend (Logs)")
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{Fore.GREEN}{Style.BRIGHT}")
        print("========================================")
        print("       Syntiox CORE SERVER LOGS         ")
        print("========================================")
        print(f"{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}[Security] External Device PIN: {auth_token}{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}[Syntiox CORE] Launching Terminal CLI...{Style.RESET_ALL}")
        if is_exe:
            os.system(f'start "Syntiox CORE Chat Interface" cmd /c "{sys.executable} --run-frontend"')
        else:
            os.system('start "Syntiox CORE Chat Interface" cmd /c "python frontend/chat_cli.py"')
        
        print(f"{Fore.GREEN}[Syntiox CORE] Log Server starting on 127.0.0.1:9999 via FastAPI{Style.RESET_ALL}")
        uvicorn.run("backend.main:app", host="0.0.0.0", port=9999, log_level="warning", access_log=False)

    else:
        # Standard 'stx' mode
        os.system("title Syntiox CORE Chat Interface")
        
        if server_running:
            # Just run the CLI, server is already running
            print(f"{Fore.CYAN}[Security] External Device PIN: {auth_token}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[Syntiox CORE] Connecting to existing background server...{Style.RESET_ALL}")
            while True:
                exit_code = 0
                try:
                    if is_exe:
                        result = subprocess.run([sys.executable, "--run-frontend"])
                    else:
                        result = subprocess.run([sys.executable, "frontend/chat_cli.py"])
                    exit_code = result.returncode
                except KeyboardInterrupt:
                    pass
                    
                if exit_code == 42:
                    print(f"{Fore.YELLOW}[Syntiox CORE] Restarting system to apply new configurations...{Style.RESET_ALL}")
                    time.sleep(1)
                    continue
                else:
                    break
        else:
            # Background mode (attached): Run server silently, show CLI in this window
            print(f"{Fore.CYAN}[Security] External Device PIN: {auth_token}{Style.RESET_ALL}")
            
            server_process = None
            def cleanup_server():
                if server_process:
                    server_process.terminate()
            atexit.register(cleanup_server)

            while True:
                print(f"{Fore.GREEN}[Syntiox CORE] Starting background server on 0.0.0.0:9999...{Style.RESET_ALL}")
                
                # By NOT using CREATE_NO_WINDOW, the background process attaches to THIS terminal.
                if is_exe:
                    cmd = [sys.executable, "--run-backend"]
                else:
                    cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9999", "--log-level", "warning"]

                server_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                time.sleep(2)  # Wait for server to start
                
                exit_code = 0
                try:
                    # Run the Textual CLI in this exact window
                    if is_exe:
                        result = subprocess.run([sys.executable, "--run-frontend"])
                    else:
                        result = subprocess.run([sys.executable, "frontend/chat_cli.py"])
                    exit_code = result.returncode
                except KeyboardInterrupt:
                    pass
                finally:
                    if server_process:
                        server_process.terminate()
                        try:
                            server_process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            server_process.kill()
                            
                if exit_code == 42:
                    print(f"{Fore.YELLOW}[Syntiox CORE] Restarting system to apply new configurations...{Style.RESET_ALL}")
                    time.sleep(1)
                    continue
                else:
                    break
