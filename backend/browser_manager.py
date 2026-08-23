# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import time
import os
import sys

def start_persistent_browser():
    from backend.config_paths import WORKSPACE_DIR
    data_dir = os.path.join(WORKSPACE_DIR, "browser_data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        
    print(f"Starting persistent browser on port 9222 with data dir: {data_dir}")
    
    # Check for Brave Browser
    brave_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")
    ]
    
    executable_path = None
    channel = "chrome"
    
    for path in brave_paths:
        if os.path.exists(path):
            executable_path = path
            channel = None # Disables channel if we use executable_path
            print(f"Brave Browser found at: {path}. Using Brave for AdBlocking.")
            break
            
    if not executable_path:
        print("Brave not found, falling back to Google Chrome.")
    
    with sync_playwright() as p:
        try:
            launch_args = {
                "user_data_dir": data_dir,
                "headless": False,
                "no_viewport": True,
                "args": [
                    "--remote-debugging-port=9222",
                    "--start-maximized",
                    "--window-position=0,0",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-features=CalculateNativeWinOcclusion",
                    "--autoplay-policy=no-user-gesture-required",
                    "--disable-blink-features=AutomationControlled"
                ],
                "ignore_default_args": [
                    "--enable-automation", 
                    "--disable-extensions", 
                    "--disable-component-extensions-with-background-pages",
                    "--disable-component-update"
                ]
            }
            
            if executable_path:
                launch_args["executable_path"] = executable_path
            else:
                launch_args["channel"] = channel

            context = p.chromium.launch_persistent_context(**launch_args)
            print("Browser running successfully.")
            
            # Keep the process alive so the browser stays open
            while True:
                time.sleep(1)
        except Exception as e:
            print(f"Failed to start browser: {e}")
            sys.exit(1)

if __name__ == "__main__":
    start_persistent_browser()
