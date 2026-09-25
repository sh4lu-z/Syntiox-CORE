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
        let els = document.querySelectorAll('a, button, input, textarea, [role="button"], [role="link"], select');
        els.forEach((el) => {
            let rect = el.getBoundingClientRect();
            // Check if element is visible and in viewport
            if (rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.bottom <= (window.innerHeight || document.documentElement.clientHeight)) {
                let text = (el.innerText || el.value || el.placeholder || el.id || el.getAttribute('aria-label') || 'Unknown').trim().substring(0, 60);
                text = text.replace(/\\n/g, ' ');
                if (text && text !== 'Unknown') {
                    let agentId = items.length + 1;
                    el.setAttribute('agent-id', agentId);
                    items.push('[' + agentId + '] ' + el.tagName.toLowerCase() + ' : ' + text);
                }
            }
        });
        return { text: document.body.innerText.substring(0, 800), elements: items.slice(0, 50) };
    }
    """
    try:
        data = page.evaluate(js_script)
        print("\n--- PAGE CONTENT SUMMARY ---")
        print(data['text'])
        print("\n--- INTERACTABLE ELEMENTS (ON SCREEN) ---")
        for item in data['elements']:
            print(item)
        print("-----------------------------------------\n")
    except Exception as e:
        print(f"[TEXT_RESULT] Error extracting DOM: {e}")

def _feedback(page):
    from backend.config_paths import ENV_FILE
    load_dotenv(ENV_FILE)
    vision_enabled = os.getenv("VISION_ENABLED", "false").lower() == "true"
    
    if vision_enabled:
        screenshot_path = os.path.join(os.getcwd(), "browser_view.png")
        page.screenshot(path=screenshot_path)
        print(f"[IMAGE_RESULT] {screenshot_path}")
    
    # Always dump the text/DOM mapping for accuracy
    _get_dom_text(page)
    print("[TEXT_RESULT] Page extracted successfully. Use the [ID] numbers for interactions.")

def _execute_with_playwright(action_func):
    _ensure_browser_running()
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            action_func(page)
        except Exception as e:
            print(f"[ERROR] Browser interaction failed: {e}")

# --- Public API for Agent ---

def goto(url: str):
    def _action(page):
        print(f"Navigating to {url}...")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[WARNING] Navigation took too long or failed partially: {e}")
        _feedback(page)
    _execute_with_playwright(_action)

def click(element_id: str):
    def _action(page):
        print(f"Clicking element ID [{element_id}]...")
        selector = f"[agent-id='{element_id}']"
        try:
            page.click(selector, timeout=3000, force=True)
            page.wait_for_timeout(2000)
            _feedback(page)
        except Exception as e:
            print(f"[WARNING] Standard click failed, trying JavaScript click...")
            try:
                page.evaluate(f"document.querySelector(\"{selector}\").click()")
                page.wait_for_timeout(2000)
                _feedback(page)
            except Exception as js_e:
                print(f"[ERROR] Could not click element ID [{element_id}]. Ensure it exists in the list or try scrolling.")
                _feedback(page)
    _execute_with_playwright(_action)

def type_text(element_id: str, text: str):
    def _action(page):
        print(f"Typing into element ID [{element_id}]...")
        selector = f"[agent-id='{element_id}']"
        try:
            page.fill(selector, text, timeout=3000, force=True)
            page.wait_for_timeout(1000)
            _feedback(page)
        except Exception as e:
            print(f"[WARNING] Standard typing failed, trying JavaScript value injection...")
            try:
                # Escape text for JS
                js_text = text.replace("'", "\\'").replace('"', '\\"')
                page.evaluate(f"document.querySelector(\"{selector}\").value = '{js_text}'")
                page.wait_for_timeout(1000)
                _feedback(page)
            except Exception as js_e:
                print(f"[ERROR] Could not type in element ID [{element_id}].")
                _feedback(page)
    _execute_with_playwright(_action)

def press_key(element_id: str, key: str):
    """Press a keyboard key on a focused element."""
    def _action(page):
        print(f"Pressing '{key}' on element ID [{element_id}]...")
        selector = f"[agent-id='{element_id}']"
        try:
            page.press(selector, key, timeout=5000)
            page.wait_for_timeout(2000)
            _feedback(page)
        except Exception as e:
            print(f"[ERROR] Could not press key on element ID [{element_id}].")
            _feedback(page)
    _execute_with_playwright(_action)

def press_enter(element_id: str):
    """Shortcut to press Enter on an element."""
    press_key(element_id, "Enter")

def extract():
    def _action(page):
        _feedback(page)
    _execute_with_playwright(_action)

def scroll_down():
    def _action(page):
        print("Scrolling down...")
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(1500)
        _feedback(page)
    _execute_with_playwright(_action)

def scroll_up():
    def _action(page):
        print("Scrolling up...")
        page.mouse.wheel(0, -600)
        page.wait_for_timeout(1500)
        _feedback(page)
    _execute_with_playwright(_action)

