# -*- coding: utf-8 -*-
import subprocess
import time
import os
import sys

def start_persistent_browser():
    # Ensure root directory is in sys.path
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    from backend.config_paths import WORKSPACE_DIR
    data_dir = os.path.join(WORKSPACE_DIR, "browser_data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        
    # Clear previous sessions to prevent tabs from restoring automatically
    import shutil
    sessions_dir = os.path.join(data_dir, "Default", "Sessions")
    if os.path.exists(sessions_dir):
        try:
            shutil.rmtree(sessions_dir)
        except Exception:
            pass
            
    print(f"Starting persistent browser on port 9222 with data dir: {data_dir}")
    
    # Check for Brave Browser
    brave_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")
    ]
    
    executable_path = next((p for p in brave_paths if os.path.exists(p)), None)
    if not executable_path:
        executable_path = "chrome.exe"
        print("Brave not found, falling back to Google Chrome.")
    else:
        print(f"Brave Browser found at: {executable_path}. Using Brave for AdBlocking.")
    
    try:
        args = [
            executable_path,
            f"--user-data-dir={data_dir}",
            "--remote-debugging-port=9222",
            "--start-maximized",
            "--window-position=0,0",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=CalculateNativeWinOcclusion",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check"
        ]
        
        proc = subprocess.Popen(args)
        print("Browser running successfully.")
        
        # Exit together with the browser so no stale manager is left running
        try:
            proc.wait()
        except (KeyboardInterrupt, SystemExit):
            print("Browser shutting down gracefully...")
            proc.terminate()
            
    except Exception as e:
        print(f"Failed to start browser: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_persistent_browser()
