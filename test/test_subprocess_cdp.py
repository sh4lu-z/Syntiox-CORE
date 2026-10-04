import os
import sys
import time
import subprocess
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
if not executable_path:
    executable_path = "chrome.exe"

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

print("Launching browser directly via subprocess...")
proc = subprocess.Popen(args)
time.sleep(3)

try:
    print("--- Step 1: Connect CDP & Navigate Tab 1 ---")
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = b.contexts[0]
        p1 = ctx.pages[0] if ctx.pages else ctx.new_page()
        p1.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=15000)
        print("Tab 1 title:", p1.title())

    print("--- Step 2: Connect CDP & Create Tab 2 with new_tab ---")
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = b.contexts[0]
        print(f"Before new_page, pages count = {len(ctx.pages)}")
        p2 = ctx.new_page()
        print(f"After new_page, pages count = {len(ctx.pages)}")
        print("Tab 2 created. URL:", p2.url)
        p2.goto("https://www.google.com/search?q=Rust+vs+Go", wait_until="domcontentloaded", timeout=15000)
        print("Tab 2 navigated! Title:", p2.title())

    print("--- Step 3: Connect CDP & Check Tab 2 state ---")
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp("http://localhost:9222")
        ctx = b.contexts[0]
        print(f"Current pages count in CDP: {len(ctx.pages)}")
        for idx, page in enumerate(ctx.pages):
            print(f"Page [{idx}] Title: '{page.title()}' | URL: {page.url}")

finally:
    time.sleep(2)
    proc.terminate()
