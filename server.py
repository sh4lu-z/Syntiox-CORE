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
    os.system("chcp 65001 > nul")
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
    
    # Start FastAPI app
    uvicorn.run("backend.main:app", host="127.0.0.1", port=9999, log_level="warning", access_log=False)
