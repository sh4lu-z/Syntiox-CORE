# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import urllib.request
import subprocess
import time
import os
import sys
import base64
from dotenv import load_dotenv

def _ensure_browser_running():
    try:
        urllib.request.urlopen("http://localhost:9222/json/version", timeout=1)
    except:
        print("Starting background browser on port 9222...")
        script_path = os.path.join(os.path.dirname(__file__), "browser_manager.py")
        cmd = f'"{sys.executable}" "{script_path}"'
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)

def _get_dom_text(page):
    js_script = """
    () => {
        let items = [];
        let els = document.querySelectorAll('a, button, input, textarea');
        els.forEach(el => {
            let rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                let text = (el.innerText || el.value || el.placeholder || el.id || 'Unknown').trim().substring(0, 50);
                if (text && text !== 'Unknown') {
                    items.push('[' + el.tagName + '] ' + text);
                }
            }
        });
        return { text: document.body.innerText.substring(0, 1000), elements: items.slice(0, 40) };
    }
    """
    data = page.evaluate(js_script)
    print("\n--- PAGE CONTENT (TEXT) ---")
    print(data['text'])
    print("\n--- INTERACTABLE ELEMENTS ---")
    for idx, item in enumerate(data['elements']):
        print(f"[{idx}] {item}")
    print("---------------------------\n")

def _feedback(page):
    from backend.config_paths import ENV_FILE
    load_dotenv(ENV_FILE)
    vision_enabled = os.getenv("VISION_ENABLED", "false").lower() == "true"
    
    if vision_enabled:
        screenshot_path = os.path.join(os.getcwd(), "browser_view.png")
        page.screenshot(path=screenshot_path)
        print(f"[IMAGE_RESULT] {screenshot_path}")
    else:
        _get_dom_text(page)
        print("[TEXT_RESULT] Page DOM extracted successfully.")

def _execute_with_playwright(action_func):
    _ensure_browser_running()
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        action_func(page)

# --- Public API for Agent ---

def goto(url: str):
    def _action(page):
        print(f"Navigating to {url}...")
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        _feedback(page)
    _execute_with_playwright(_action)

def click(selector: str):
    def _action(page):
        print(f"Clicking {selector}...")
        page.click(selector, timeout=5000)
        page.wait_for_timeout(2000)
        _feedback(page)
    _execute_with_playwright(_action)

def type_text(selector: str, text: str):
    def _action(page):
        print(f"Typing into {selector}...")
        page.fill(selector, text, timeout=5000)
        page.wait_for_timeout(1000)
        _feedback(page)
    _execute_with_playwright(_action)

def press_key(selector: str, key: str):
    """Press a keyboard key on a focused element. e.g. press_key('input[name=q]', 'Enter')"""
    def _action(page):
        print(f"Pressing '{key}' on {selector}...")
        page.press(selector, key, timeout=5000)
        page.wait_for_timeout(2000)
        _feedback(page)
    _execute_with_playwright(_action)

def press_enter(selector: str):
    """Shortcut to press Enter on a focused element."""
    press_key(selector, "Enter")

def extract():
    def _action(page):
        _feedback(page)
    _execute_with_playwright(_action)
