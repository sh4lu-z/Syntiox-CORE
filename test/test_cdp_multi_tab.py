import os
import sys
import time
import subprocess
from playwright.sync_api import sync_playwright

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 1. Start browser_manager if not running
proc = subprocess.Popen([sys.executable, os.path.join(root_dir, "backend", "browser_manager.py")])
time.sleep(4)

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
    time.sleep(3)
    proc.terminate()
