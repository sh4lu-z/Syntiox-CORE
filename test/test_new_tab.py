import os
import sys
import time
from playwright.sync_api import sync_playwright

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.config_paths import WORKSPACE_DIR
data_dir = os.path.join(WORKSPACE_DIR, "browser_data")

brave_paths = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")
]
executable_path = next((p for p in brave_paths if os.path.exists(p)), None)

with sync_playwright() as p:
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
    
    print("Launching persistent context...")
    context = p.chromium.launch_persistent_context(**launch_args)
    page1 = context.pages[0] if context.pages else context.new_page()
    print("Navigating Tab 1 to youtube.com...")
    page1.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=15000)
    print("Tab 1 title:", page1.title())
    
    time.sleep(2)
    print("Opening Tab 2...")
    page2 = context.new_page()
    print("Navigating Tab 2 to google.com...")
    try:
        page2.goto("https://www.google.com/search?q=Rust+vs+Go", wait_until="domcontentloaded", timeout=15000)
        print("Tab 2 title:", page2.title())
        print("Tab 2 URL:", page2.url)
    except Exception as e:
        print("Tab 2 navigation failed:", e)
    
    time.sleep(5)
    context.close()
