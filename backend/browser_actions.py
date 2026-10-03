# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import urllib.request
import subprocess
import time
import os
import sys
from dotenv import load_dotenv

_CURRENT_TAB_INDEX = 0

def bring_browser_to_front():
    """Bring the persistent browser window to the foreground on Windows."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        found_hwnds = []

        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    if any(k in title for k in ["brave", "chrome", "syntiox"]):
                        found_hwnds.append(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        for h in found_hwnds:
            user32.ShowWindow(h, 9)  # SW_RESTORE
            user32.SetForegroundWindow(h)
            break
    except Exception:
        pass

def _ensure_browser_running():
    try:
        urllib.request.urlopen("http://localhost:9222/json/version", timeout=1)
    except Exception:
        print("Starting background browser on port 9222...")
        script_path = os.path.join(os.path.dirname(__file__), "browser_manager.py")
        cmd = f'"{sys.executable}" "{script_path}"'
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)

def _ensure_overlay(page):
    """Ensures the Syntiox overlay script is running in the page."""
    try:
        loaded = page.evaluate("() => typeof window.__syntiox !== 'undefined'")
        if not loaded:
            overlay_path = os.path.join(os.path.dirname(__file__), "browser_overlay.js")
            if os.path.exists(overlay_path):
                with open(overlay_path, "r", encoding="utf-8") as f:
                    js = f.read()
                page.evaluate(f"(() => {{ const fn = {js}; fn(); }})()")
    except Exception:
        pass

def _set_overlay(page, active=True, alive=True, mode="work", status="", cursor=None):
    _ensure_overlay(page)
    try:
        page.evaluate("""(state) => {
            if (window.__syntiox) {
                window.__syntiox.apply(state);
            }
        }""", {
            "active": active,
            "alive": alive,
            "mode": mode,
            "status": status,
            "cursor": cursor
        })
    except Exception:
        pass

def _animate_to_element(page, element_id: str, action_desc: str = ""):
    """Smoothly moves the visible agent cursor to the element, highlights it, and triggers ripple."""
    _ensure_overlay(page)
    if action_desc:
        _set_overlay(page, active=True, alive=True, mode="work", status=action_desc)

    selector = f"[agent-id='{element_id}']"
    script = f"""
    (() => {{
        const el = document.querySelector("{selector}");
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {{
            x: Math.round(r.left + r.width / 2),
            y: Math.round(r.top + r.height / 2),
            rect: {{ x: Math.round(r.left), y: Math.round(r.top), width: Math.round(r.width), height: Math.round(r.height) }}
        }};
    }})()
    """
    try:
        coords = page.evaluate(script)
        if coords and "x" in coords and "y" in coords:
            x, y = coords["x"], coords["y"]
            rect = coords.get("rect")
            page.evaluate("""([x, y, rect]) => {
                if (window.__syntiox) {
                    window.__syntiox.moveTo(x, y);
                    if (rect) window.__syntiox.highlight(rect, 900);
                }
            }""", [x, y, rect])
            time.sleep(0.35)
            page.evaluate("([x, y]) => window.__syntiox?.ripple?.(x, y)", [x, y])
            time.sleep(0.15)
            return True
    except Exception:
        pass
    return False

def _get_dom_text(page, offset: int = 0, length: int = 2000):
    js_script = f"""
    () => {{
        let items = [];
        // Primary interactable elements
        let sel = 'a, button, input, textarea, select, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [role="checkbox"], [role="switch"], [onclick], [tabindex="0"]';
        let els = Array.from(document.querySelectorAll(sel));

        // Catch clickable divs or spans styled as pointer buttons
        let clickableDivs = Array.from(document.querySelectorAll('div, span, li')).filter(el => {{
            if (els.includes(el)) return false;
            let style = window.getComputedStyle(el);
            return style.cursor === 'pointer' && el.children.length <= 2;
        }});
        
        let allEls = els.concat(clickableDivs);

        allEls.forEach((el) => {{
            let rect = el.getBoundingClientRect();
            // Element is visible and in viewport
            if (rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.bottom <= (window.innerHeight || document.documentElement.clientHeight)) {{
                let text = (el.innerText || el.value || el.placeholder || el.id || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim().substring(0, 70);
                text = text.replace(/\\n/g, ' ');
                if (text) {{
                    let agentId = items.length + 1;
                    el.setAttribute('agent-id', agentId);
                    items.push('[' + agentId + '] ' + el.tagName.toLowerCase() + ' : ' + text);
                }}
            }}
        }});

        let fullText = (document.body ? document.body.innerText : '') || '';
        let totalLen = fullText.length;
        let slicedText = fullText.substring({offset}, {offset + length});

        return {{
            text: slicedText,
            total_length: totalLen,
            offset: {offset},
            length: {length},
            elements: items.slice(0, 75)
        }};
    }}
    """
    try:
        data = page.evaluate(js_script)
        total_len = data.get('total_length', 0)
        curr_offset = data.get('offset', 0)
        print("\n--- PAGE CONTENT SUMMARY ---")
        print(data['text'])
        if total_len > curr_offset + length:
            print(f"\n[Note: Page has {total_len} total characters. Showing {curr_offset} to {curr_offset + length}. Call extract(offset={curr_offset + length}) to read more.]")
        print("\n--- INTERACTABLE ELEMENTS (ON SCREEN) ---")
        for item in data['elements']:
            print(item)
        print("-----------------------------------------\n")
    except Exception as e:
        print(f"[TEXT_RESULT] Error extracting DOM: {e}")

def _feedback(page, offset: int = 0, length: int = 2000):
    from backend.config_paths import ENV_FILE
    load_dotenv(ENV_FILE)
    vision_enabled = os.getenv("VISION_ENABLED", "false").lower() == "true"
    
    if vision_enabled:
        screenshot_path = os.path.join(os.getcwd(), "browser_view.png")
        try:
            # Hide overlay briefly during screenshot so it does not obstruct the view
            page.evaluate("() => window.__syntiox?.capture?.(true)")
            page.screenshot(path=screenshot_path)
            page.evaluate("() => window.__syntiox?.capture?.(false)")
            print(f"[IMAGE_RESULT] {screenshot_path}")
        except Exception:
            pass
    
    _get_dom_text(page, offset=offset, length=length)
    print("[TEXT_RESULT] Page extracted successfully. Use the [ID] numbers for interactions.")

def _execute_with_playwright(action_func):
    global _CURRENT_TAB_INDEX
    _ensure_browser_running()
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            pages = context.pages
            if not pages:
                page = context.new_page()
            elif _CURRENT_TAB_INDEX < len(pages):
                page = pages[_CURRENT_TAB_INDEX]
            else:
                page = pages[-1]
                _CURRENT_TAB_INDEX = len(pages) - 1

            _ensure_overlay(page)
            action_func(page, context)
        except Exception as e:
            print(f"[ERROR] Browser interaction failed: {e}")

# --- Public API for Agent ---

def set_agent_active(active: bool, task_name: str = ""):
    """Sets overlay active status and brings window to front."""
    if active:
        bring_browser_to_front()
    def _action(page, context):
        _set_overlay(page, active=active, alive=active, mode="work", status=f"Working: {task_name}" if task_name else "Agent active")
    _execute_with_playwright(_action)

def goto(url: str):
    def _action(page, context):
        print(f"Navigating to {url}...")
        _set_overlay(page, active=True, alive=True, mode="work", status=f"Navigating to {url}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[WARNING] Navigation took too long or failed partially: {e}")
        _ensure_overlay(page)
        _set_overlay(page, active=True, alive=True, mode="work", status="Page loaded")
        _feedback(page)
    _execute_with_playwright(_action)

def click(element_id: str):
    def _action(page, context):
        print(f"Clicking element ID [{element_id}]...")
        selector = f"[agent-id='{element_id}']"
        _animate_to_element(page, element_id, action_desc=f"Clicking element [{element_id}]")
        
        # Briefly pass blocker so synthetic/Playwright click triggers target
        page.evaluate("() => window.__syntiox?.pass?.(true)")
        try:
            page.click(selector, timeout=3000, force=True)
            page.wait_for_timeout(1500)
            page.evaluate("() => window.__syntiox?.pass?.(false)")
            _feedback(page)
        except Exception as e:
            print(f"[WARNING] Standard click failed, trying JavaScript click...")
            try:
                page.evaluate(f"document.querySelector(\"{selector}\").click()")
                page.wait_for_timeout(1500)
                page.evaluate("() => window.__syntiox?.pass?.(false)")
                _feedback(page)
            except Exception as js_e:
                page.evaluate("() => window.__syntiox?.pass?.(false)")
                print(f"[ERROR] Could not click element ID [{element_id}]. Ensure it exists in the list or try scrolling.")
                _feedback(page)
    _execute_with_playwright(_action)

def type_text(element_id: str, text: str):
    def _action(page, context):
        print(f"Typing into element ID [{element_id}]...")
        selector = f"[agent-id='{element_id}']"
        _animate_to_element(page, element_id, action_desc=f"Typing text into [{element_id}]")

        page.evaluate("() => window.__syntiox?.pass?.(true)")
        try:
            page.click(selector, timeout=2000, force=True)
            page.fill(selector, "")  # Clear existing input
            # Realistic letter-by-letter typing animation
            page.type(selector, text, delay=35)
            page.wait_for_timeout(800)
            page.evaluate("() => window.__syntiox?.pass?.(false)")
            _feedback(page)
        except Exception as e:
            print(f"[WARNING] Standard typing failed, trying JavaScript value injection...")
            try:
                js_text = text.replace("'", "\\'").replace('"', '\\"')
                page.evaluate(f"""(function() {{
                    var el = document.querySelector("{selector}");
                    if (el) {{
                        el.value = '{js_text}';
                        el.dispatchEvent(new Event('input', {{bubbles: true}}));
                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }}
                }})()""")
                page.wait_for_timeout(800)
                page.evaluate("() => window.__syntiox?.pass?.(false)")
                _feedback(page)
            except Exception as js_e:
                page.evaluate("() => window.__syntiox?.pass?.(false)")
                print(f"[ERROR] Could not type in element ID [{element_id}].")
                _feedback(page)
    _execute_with_playwright(_action)

def press_key(element_id: str, key: str):
    """Press a keyboard key on a focused element."""
    def _action(page, context):
        print(f"Pressing '{key}' on element ID [{element_id}]...")
        selector = f"[agent-id='{element_id}']"
        _animate_to_element(page, element_id, action_desc=f"Pressing {key}")
        page.evaluate("() => window.__syntiox?.pass?.(true)")
        try:
            page.press(selector, key, timeout=5000)
            page.wait_for_timeout(1500)
            page.evaluate("() => window.__syntiox?.pass?.(false)")
            _feedback(page)
        except Exception as e:
            page.evaluate("() => window.__syntiox?.pass?.(false)")
            print(f"[ERROR] Could not press key on element ID [{element_id}].")
            _feedback(page)
    _execute_with_playwright(_action)

def press_enter(element_id: str):
    """Shortcut to press Enter on an element."""
    press_key(element_id, "Enter")

def extract(offset: int = 0, length: int = 2000):
    """Extract page content and elements. Use offset to read further down in the text."""
    def _action(page, context):
        _feedback(page, offset=offset, length=length)
    _execute_with_playwright(_action)

def scroll_down():
    def _action(page, context):
        print("Scrolling down...")
        _set_overlay(page, active=True, alive=True, mode="work", status="Scrolling down")
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(1500)
        _feedback(page)
    _execute_with_playwright(_action)

def scroll_up():
    def _action(page, context):
        print("Scrolling up...")
        _set_overlay(page, active=True, alive=True, mode="work", status="Scrolling up")
        page.mouse.wheel(0, -600)
        page.wait_for_timeout(1500)
        _feedback(page)
    _execute_with_playwright(_action)

# --- Tab Management ---

def new_tab(url: str = ""):
    """Opens a new browser tab and optionally navigates to a URL."""
    global _CURRENT_TAB_INDEX
    def _action(page, context):
        global _CURRENT_TAB_INDEX
        print(f"Opening new tab: {url or 'blank'}...")
        new_p = context.new_page()
        _CURRENT_TAB_INDEX = len(context.pages) - 1
        _ensure_overlay(new_p)
        _set_overlay(new_p, active=True, alive=True, mode="work", status="New tab opened")
        if url:
            new_p.goto(url, wait_until="domcontentloaded", timeout=15000)
            new_p.wait_for_timeout(1500)
        _feedback(new_p)
    _execute_with_playwright(_action)

def switch_tab(index: int):
    """Switches the active tab to the specified tab index (0, 1, 2...)."""
    global _CURRENT_TAB_INDEX
    def _action(page, context):
        global _CURRENT_TAB_INDEX
        pages = context.pages
        if 0 <= index < len(pages):
            _CURRENT_TAB_INDEX = index
            target_p = pages[index]
            target_p.bring_to_front()
            _ensure_overlay(target_p)
            _set_overlay(target_p, active=True, alive=True, mode="work", status=f"Switched to tab {index}")
            print(f"Switched to tab {index}: {target_p.title()}")
            _feedback(target_p)
        else:
            print(f"[ERROR] Invalid tab index {index}. Total tabs: {len(pages)}")
    _execute_with_playwright(_action)

def close_tab(index: int = -1):
    """Closes a tab. If index is -1, closes the current active tab."""
    global _CURRENT_TAB_INDEX
    def _action(page, context):
        global _CURRENT_TAB_INDEX
        pages = context.pages
        target_idx = _CURRENT_TAB_INDEX if index == -1 else index
        if 0 <= target_idx < len(pages):
            closing_page = pages[target_idx]
            print(f"Closing tab {target_idx}: {closing_page.title()}...")
            closing_page.close()
            remaining = context.pages
            _CURRENT_TAB_INDEX = max(0, min(target_idx, len(remaining) - 1))
            if remaining:
                remaining[_CURRENT_TAB_INDEX].bring_to_front()
                _feedback(remaining[_CURRENT_TAB_INDEX])
            else:
                print("All tabs closed.")
        else:
            print(f"[ERROR] Cannot close tab {target_idx}. Total tabs: {len(pages)}")
    _execute_with_playwright(_action)

def list_tabs():
    """Lists all open tabs with their indices, titles, and URLs."""
    def _action(page, context):
        pages = context.pages
        print(f"\n--- OPEN BROWSER TABS ({len(pages)}) ---")
        for i, p in enumerate(pages):
            marker = " (ACTIVE)" if i == _CURRENT_TAB_INDEX else ""
            print(f"[{i}]{marker} {p.title()} - {p.url}")
        print("---------------------------------------\n")
    _execute_with_playwright(_action)

# --- Human Intervention (CAPTCHA / Login) ---

def request_human_intervention(reason: str, timeout_seconds: int = 300) -> str:
    """
    Hands over browser control to the human user for CAPTCHA, 2FA, or login.
    Unblocks the browser, displays an amber banner with reason and a 'Continue' button.
    Waits until the user clicks 'Continue' or timeout expires.
    """
    bring_browser_to_front()
    print(f"\n⚠️ [HUMAN INTERVENTION REQUIRED]: {reason}")
    print("Browser control handed over to user. Solve the captcha/login in the browser and click 'Continue' or press Enter in terminal.\n")

    def _prepare(page, context):
        _ensure_overlay(page)
        page.evaluate("""(reason) => {
            if (window.__syntiox) {
                window.__syntiox.apply({
                    active: true,
                    alive: true,
                    mode: 'handoff',
                    status: reason,
                    handoff_done: false
                });
            }
        }""", reason)
    _execute_with_playwright(_prepare)

    # Poll for user completion in the browser overlay
    start_time = time.time()
    user_continued = False

    while time.time() - start_time < timeout_seconds:
        def _check(page, context):
            nonlocal user_continued
            try:
                state = page.evaluate("() => window.__syntiox ? window.__syntiox.localState() : null")
                if state and state.get("handoff_done"):
                    user_continued = True
            except Exception:
                pass
        _execute_with_playwright(_check)

        if user_continued:
            break
        time.sleep(1.5)

    def _restore(page, context):
        _set_overlay(page, active=True, alive=True, mode="work", status="Resuming autonomous control...")
        time.sleep(0.5)
        _feedback(page)
    _execute_with_playwright(_restore)

    return "Human intervention complete. Agent resuming control."
