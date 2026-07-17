import os
import sys
import time
import asyncio
import websockets
import threading
import itertools
from colorama import init, Fore, Style

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

init(autoreset=True)

URI = 'ws://127.0.0.1:9999/ws'

is_waiting = False
current_state = "Thinking..."

def spinner():
    """Shows a spinning animation while waiting for server response."""
    spinner_chars = itertools.cycle(['|', '/', '-', '\\'])
    while is_waiting:
        sys.stdout.write(f"\r{Fore.YELLOW}{next(spinner_chars)} {current_state}...{Style.RESET_ALL}                    ")
        sys.stdout.flush()
        time.sleep(0.1)
    # Clear the line when done
    sys.stdout.write('\r' + ' ' * 30 + '\r')
    sys.stdout.flush()

async def send_to_server(command):
    global is_waiting, current_state
    try:
        async with websockets.connect(URI) as websocket:
            await websocket.send(command)
            
            is_waiting = True
            current_state = "Thinking"
            spin_thread = threading.Thread(target=spinner, daemon=True)
            spin_thread.start()
            
            final_response = ""
            receiving_final = False
            
            while True:
                text = await websocket.recv()
                
                # Extract states
                while "[STATE:" in text:
                    start_idx = text.find("[STATE:")
                    end_idx = text.find("]", start_idx)
                    if end_idx != -1:
                        state_str = text[start_idx:end_idx+1]
                        current_state = state_str.replace("[STATE:", "").replace("]", "")
                        text = text.replace(state_str, "")
                    else:
                        break # Incomplete state packet
                
                if "[FINAL]" in text:
                    receiving_final = True
                    text = text.split("[FINAL]")[1]
                    
                if receiving_final:
                    if "[DONE]" in text:
                        final_response += text.replace("[DONE]", "")
                        break
                    final_response += text
            
            is_waiting = False
            spin_thread.join()
            
            if final_response:
                print(f"\n{Fore.GREEN}Syntiox CORE:{Style.RESET_ALL} {final_response.strip()}\n")
            else:
                print(f"\n{Fore.RED}Syntiox CORE: No response from server.{Style.RESET_ALL}\n")
    except ConnectionRefusedError:
        is_waiting = False
        print(f"\n{Fore.RED}Error: Cannot connect to Syntiox CORE Server. Is server.py running?{Style.RESET_ALL}\n")
    except Exception as e:
        is_waiting = False
        print(f"\n{Fore.RED}Error: {e}{Style.RESET_ALL}\n")

def main():
    os.system("chcp 65001 > nul")
    os.system("title Syntiox CORE Chat Interface")
    os.system("cls" if os.name == "nt" else "clear")
    
    logo_lines = [
        r"  ____              _   _                ____   ___   ____   _____ ",
        r" / ___| _   _ _ __ | |_(_) ___  __  __  / ___| / _ \ |  _ \ | ____|",
        r" \___ \| | | | '_ \| __| |/ _ \ \ \/ / | |    | | | || |_) ||  _|  ",
        r"  ___) | |_| | | | | |_| | (_) | >  <  | |___ | |_| ||  _ < | |___ ",
        r" |____/ \__, |_| |_|\__|_|\___/ /_/\_\  \____| \___/ |_| \_\|_____|",
        r"        |___/                                                      "
    ]
    
    print()
    for line in logo_lines:
        part1 = line[:39]
        part2 = line[39:]
        print(f"{Fore.CYAN}{Style.BRIGHT}{part1}{Fore.MAGENTA}{Style.BRIGHT}{part2}{Style.RESET_ALL}")
    
    print(f"\n{Fore.LIGHTBLACK_EX}Type your message or say 'Hey Syntiox' to speak.{Style.RESET_ALL}\n")
    
    try:
        while True:
            # Wait a bit before input to allow startup prints to settle
            time.sleep(0.1)
            user_input = input(f"{Fore.CYAN}You:{Style.RESET_ALL} ")
            if not user_input.strip():
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                break
                
            try:
                asyncio.run(send_to_server(user_input))
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Stopping process...{Style.RESET_ALL}")
                try:
                    import requests
                    requests.get("http://127.0.0.1:9999/stop", timeout=2)
                except Exception:
                    pass
            
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n{Fore.GREEN}Goodbye.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
