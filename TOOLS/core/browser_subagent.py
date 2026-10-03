import os
import sys
import json
import io
import time
from contextlib import redirect_stdout
from TOOLS.core.logger import action_logger

@action_logger("browser_subagent")
def browser_subagent(task: str) -> str:
    """
    Start a browser subagent to perform actions in the browser with the given task description.
    The subagent will autonomously navigate, click, type, manage tabs, and request human help when needed.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    from backend import state
    from backend import browser_actions
    from backend.cloud_llm import safe_generate_content
    from google.genai import types

    def extract_tool_calls(text: str) -> list:
        import re, json
        tool_calls = []
        safe_text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(pattern, safe_text, flags=re.DOTALL):
            try:
                parsed = json.loads(match.group(1))
                if "name" in parsed:
                    tool_calls.append({"function": {"name": parsed["name"], "arguments": parsed.get("arguments", {})}})
            except Exception:
                pass
        return tool_calls
        
    sys_prompt = (
        "You are an advanced Browser Subagent. Your goal is to complete the user's task using the browser.\n"
        "You have direct control over the browser. All interactions show visual animations (custom cursor, ripples, element highlights).\n"
        "Use the EXACT XML format to call tools:\n"
        "<tool_call>{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"val\"}}</tool_call>\n\n"
        "AVAILABLE TOOLS:\n"
        "1. goto(url: string) - Navigate to URL.\n"
        "2. click(element_id: string) - Click an interactable element using its [ID].\n"
        "3. type_text(element_id: string, text: string) - Type text into an element with human-like typing.\n"
        "4. press_key(element_id: string, key: string) - Press a key (e.g., 'Enter', 'Escape', 'Tab').\n"
        "5. press_enter(element_id: string) - Shortcut to press Enter on an element.\n"
        "6. scroll_down() - Scroll down the page.\n"
        "7. scroll_up() - Scroll up the page.\n"
        "8. extract(offset: int, length: int) - Read page text and elements. If text is long, pass offset to read more.\n"
        "9. new_tab(url: string) - Open a new tab (optionally with URL).\n"
        "10. switch_tab(index: int) - Switch to tab index (0, 1, 2...).\n"
        "11. close_tab(index: int) - Close tab index (or -1 for current tab).\n"
        "12. list_tabs() - List all open tabs.\n"
        "13. request_human_intervention(reason: string) - CALL THIS IMMEDIATELY if you hit a CAPTCHA, Cloudflare verification, 2FA, or Login screen. "
        "The browser will unlock for the human user to solve it, and return control to you once done.\n\n"
        "CRITICAL RULES:\n"
        "- Always inspect [TEXT_RESULT] and [CURRENT PAGE] after each action to see updated element [ID]s, text, and URL.\n"
        "- Direct URLs: You can navigate directly to search URLs (e.g. goto('https://www.youtube.com/results?search_query=...')) to save steps.\n"
        "- Inspect Links [href]: Links show their destination like `[href: /...]`. When looking for a PLAYLIST on YouTube, specifically look for links containing `list=` or `playlist` in their [href] or text like 'Mix', 'View full playlist', or 'Play all'. Do NOT click a single video or channel link when asked for a playlist.\n"
        "- Verification: Check the [CURRENT PAGE] URL to ensure the playlist is active (URL contains `list=`).\n"
        "- If you encounter CAPTCHA / Cloudflare Turnstile / Robot checks / Login, DO NOT try to bypass it yourself. Call request_human_intervention(reason='...').\n"
        "- When the user's task is fully accomplished, output:\n"
        "<tool_call>{\"name\": \"finish\", \"arguments\": {\"result\": \"detailed summary of what was accomplished\"}}</tool_call>."
    )
    
    print(f"\n[Browser Subagent] Initializing browser for task: {task}")
    try:
        browser_actions.set_agent_active(True, task)
    except Exception as e:
        print(f"[Browser Subagent] Note on active setup: {e}")

    history = [{"role": "user", "content": f"Task: {task}"}]
    
    try:
        for step in range(20):
            contents = []
            for h in history:
                contents.append(types.Content(role=h["role"], parts=[types.Part.from_text(text=h["content"])]))
            
            try:
                res = safe_generate_content(contents, sys_prompt=sys_prompt)
                ai_text = res.get("content", "")
            except Exception as e:
                return f"Browser Agent Error: {e}"
                
            history.append({"role": "model", "content": ai_text})
            
            tool_calls = extract_tool_calls(ai_text)
            if not tool_calls:
                history.append({"role": "user", "content": "You did not use a tool. Please perform a browser action or call 'finish'."})
                continue
                
            execution_results = []
            finished = False
            final_result = ""
            
            for tc in tool_calls:
                t_name = tc.get("function", {}).get("name", "")
                t_args = tc.get("function", {}).get("arguments", {})
                
                if t_name == "finish":
                    finished = True
                    final_result = t_args.get("result", "Completed successfully.")
                    break
                    
                func = getattr(browser_actions, t_name, None)
                if func:
                    print(f"[Browser Subagent Step {step+1}] Executing: {t_name}({t_args})")
                    f = io.StringIO()
                    with redirect_stdout(f):
                        try:
                            func(**t_args)
                        except Exception as e:
                            print(f"Tool execution failed: {e}")
                    
                    out = f.getvalue()
                    execution_results.append(f"[Tool: {t_name}] Result:\n{out}")
                else:
                    execution_results.append(f"Error: Tool '{t_name}' not found.")
                    
            if finished:
                print(f"[Browser Subagent] Finished: {final_result}")
                return final_result
                
            history.append({"role": "user", "content": "\n".join(execution_results)})
            
        return "Browser Agent stopped after 20 steps without finishing."
    finally:
        try:
            browser_actions.set_agent_active(False)
        except Exception:
            pass
