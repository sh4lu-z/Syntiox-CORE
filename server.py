import os
import sys
import uvicorn
from colorama import init, Fore, Style

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Initialize colorama
init(autoreset=True)

if __name__ == "__main__":
    import subprocess
    import time
    import argparse
    import atexit

    parser = argparse.ArgumentParser(description="Syntiox CORE Server")
    parser.add_argument("--logs", action="store_true", help="Show the backend log terminal")
    args = parser.parse_args()

    os.system("chcp 65001 > nul")
    
    if args.logs:
        # Legacy mode: Show logs in this window, spawn CLI in a new window
        os.system("title Syntiox CORE Backend (Logs)")
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{Fore.GREEN}{Style.BRIGHT}")
        print("========================================")
        print("       Syntiox CORE SERVER LOGS         ")
        print("========================================")
        print(f"{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}[Syntiox CORE] Launching Terminal CLI...{Style.RESET_ALL}")
        os.system('start "Syntiox CORE Chat Interface" cmd /c "python backend/chat_cli.py"')
        
        print(f"{Fore.GREEN}[Syntiox CORE] Log Server starting on 127.0.0.1:9999 via FastAPI{Style.RESET_ALL}")
        uvicorn.run("backend.main:app", host="127.0.0.1", port=9999, log_level="warning", access_log=False)
    else:
        # Background mode: Run server silently, show CLI in this window
        os.system("title Syntiox CORE Chat Interface")
        print(f"{Fore.GREEN}[Syntiox CORE] Starting background server on 127.0.0.1:9999...{Style.RESET_ALL}")
        
        # By NOT using CREATE_NO_WINDOW, the background process attaches to THIS terminal.
        # This ensures that if the user clicks the 'X' to close the terminal, Windows will
        # send a kill signal to both the CLI and the background server simultaneously!
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "9999", "--log-level", "warning"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Ensure server is killed when CLI closes gracefully
        atexit.register(lambda: server_process.terminate())
        
        time.sleep(2)  # Wait for server to start
        
        try:
            # Run the Textual CLI in this exact window
            subprocess.run([sys.executable, "backend/chat_cli.py"])
        except KeyboardInterrupt:
            pass
        finally:
            server_process.terminate()
