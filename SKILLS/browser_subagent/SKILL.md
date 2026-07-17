---
name: Browser Subagent
description: Allows the agent to autonomously control a real web browser interactively (click, type, navigate) while "seeing" the results via visual feedback (screenshots).
keywords: browser, web, interact, click, type, screenshot, cdp, playwright, visual
---

# Interactive Browser Automation Skill

You have the ability to control a persistent, interactive web browser. Unlike standard blind execution, you will interact with the browser step-by-step and take screenshots after every action. The Agent Loop will automatically read your screenshots and feed them back to you in the next step so you can "see" what happened!

## CRITICAL RULES FOR INTERACTIVE BROWSING:
1. **Persistent Session**: You MUST NOT launch a new browser using `p.chromium.launch()`. Instead, you MUST connect to a persistent background browser using `connect_over_cdp("http://localhost:9222")`.
2. **Ensure Browser is Running**: Always include and call the `ensure_browser_running()` helper function in your scripts to automatically start the background browser if it's not open.
3. **Take Screenshots**: After *every* action (like clicking, typing, or navigating), you MUST take a screenshot using `page.screenshot(path="browser_view.png")`.
4. **Visual Feedback Loop**: You MUST print exactly `[IMAGE_RESULT] browser_view.png` to the console at the end of your script. This tells the Agent Loop to capture the screenshot and show it to you in the next loop!
5. **DO NOT USE GOOGLE SEARCH**: Google actively blocks Playwright bots with CAPTCHAs. If you need to search the web, ALWAYS use `https://www.startpage.com/` (which gives Google results without blocking bots).
6. **One Action Per Script**: Do not try to do 10 clicks in one script. Do one logical action (e.g., Navigate -> Screenshot), exit the script, look at the visual result, and then write the next script to click.

## Universal Boilerplate Template (ALWAYS USE THIS):
```python
# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import urllib.request
import subprocess
import time
import os

def ensure_browser_running():
    try:
        urllib.request.urlopen("http://localhost:9222/json/version", timeout=1)
        return True
    except:
        print("Starting background browser on port 9222...")
        import sys
        script_path = r"D:\01_PROJECTS\00_ACTIVE\Syntiox CORE\backend\browser_manager.py"
        cmd = f'"{sys.executable}" "{script_path}"'
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5) # Wait for it to start
        return True

def execute_browser_action():
    ensure_browser_running()
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        
        # --- DO YOUR ACTION HERE ---
        # Example: 
        # page.goto("https://www.startpage.com")
        # page.wait_for_timeout(2000)
        
        # --- ALWAYS TAKE SCREENSHOT & TRIGGER VISUAL FEEDBACK ---
        screenshot_path = os.path.join(os.getcwd(), "browser_view.png")
        page.screenshot(path=screenshot_path)
        print(f"[IMAGE_RESULT] {screenshot_path}")
        
        # Important: Do NOT call browser.close(), let it stay open!

if __name__ == "__main__":
    execute_browser_action()
```

## IMPORTANT BEST PRACTICES:
1. **Never use `networkidle` for wait states:** Sites like YouTube load data constantly. If you use `page.wait_for_load_state("networkidle")`, it will cause a TimeoutError. Always use `wait_until="domcontentloaded"` when calling `page.goto()`.
2. **Playing Media:** If the user asks you to play a video or song, DO NOT use the `webbrowser` module. Because you are using a persistent background browser (`browser_manager.py`), you can just navigate to YouTube, click the video, and exit your script! The browser will stay open and the video will keep playing!
3. **Robust Selectors:** If you search YouTube directly, the search box is `input[name="search_query"]` and video titles are `a#video-title`. Startpage search box is usually `input[name="query"]` or `input[id="q"]`. If one fails, look at the visual feedback screenshot in the next step to fix your selector!
