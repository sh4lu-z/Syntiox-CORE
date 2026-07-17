# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import time
import os
import sys

def start_persistent_browser():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "workspace", "browser_data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        
    print(f"Starting persistent browser on port 9222 with data dir: {data_dir}")
    
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=data_dir,
                channel="chrome", # Use real Google Chrome to avoid YouTube codec errors/blocks
                headless=False,
                no_viewport=True, # Allows the window to truly maximize
                args=[
                    "--remote-debugging-port=9222",
                    "--start-maximized",
                    "--window-position=0,0"
                ]
            )
            print("Browser running successfully.")
            
            # Keep the process alive so the browser stays open
            while True:
                time.sleep(1)
        except Exception as e:
            print(f"Failed to start browser: {e}")
            sys.exit(1)

if __name__ == "__main__":
    start_persistent_browser()
