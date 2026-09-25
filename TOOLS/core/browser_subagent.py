import os
import sys
import json
import io
from contextlib import redirect_stdout
from TOOLS.core.logger import action_logger

@action_logger("browser_subagent")
def browser_subagent(task: str) -> str:
    """
    Start a browser subagent to perform actions in the browser with the given task description.
    The subagent will autonomously navigate, click, type, and scroll to achieve the task.
    """
    # Ensure backend path is in sys.path
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    from backend import state
    from backend.parser import extract_tool_calls
    from backend import browser_actions
    
    is_google = getattr(state, "LLM_PROVIDER", "local").lower() == "google"
    
    if is_google:
        from backend.cloud_llm import safe_generate_content
        from google.genai import types
    else:
        from backend.llm_client import get_llm
        
    sys_prompt = (
        "You are a Browser Subagent. Your goal is to complete the user's task using the browser.\n"
        "You have access to the following tools. Use the EXACT XML format to call them:\n"
        "<tool_call>{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"val\"}}</tool_call>\n\n"
        "TOOLS:\n"
        "1. goto(url: string) - Navigate to URL.\n"
        "2. click(element_id: string) - Click an element by its ID.\n"
        "3. type_text(element_id: string, text: string) - Type text into an element.\n"
        "4. press_key(element_id: string, key: string) - Press a key (e.g., 'Enter', 'Escape').\n"
        "5. press_enter(element_id: string) - Shortcut to press Enter on an element.\n"
        "6. scroll_down() - Scroll down the page.\n"
        "7. scroll_up() - Scroll up the page.\n"
        "8. extract() - Extract the current page DOM text to read it.\n\n"
        "CRITICAL: Always read the [TEXT_RESULT] after an action to see the new page state and element IDs. "
        "When you are finished, output <tool_call>{\"name\": \"finish\", \"arguments\": {\"result\": \"your final summary of what you did and found\"}}</tool_call>."
    )
    
    history = [{"role": "user", "content": f"Task: {task}"}]
    print(f"\n[Browser Subagent] Starting task: {task}")
    
    for step in range(15):
        if is_google:
            contents = []
            for h in history:
                contents.append(types.Content(role=h["role"], parts=[types.Part.from_text(text=h["content"])]))
            
            try:
                res = safe_generate_content(contents, sys_prompt=sys_prompt)
                ai_text = res["content"]
            except Exception as e:
                return f"Browser Agent Error: {e}"
        else:
            my_llm = get_llm()
            if not my_llm: return "Local LLM not loaded."
            messages = [{"role": "system", "content": sys_prompt}] + history
            try:
                resp = my_llm.create_chat_completion(messages=messages, max_tokens=1024, temperature=0.1)
                ai_text = resp["choices"][0]["message"]["content"]
            except Exception as e:
                return f"Local LLM Error: {e}"
                
        history.append({"role": "model" if is_google else "assistant", "content": ai_text})
        
        tool_calls = extract_tool_calls(ai_text)
        if not tool_calls:
            history.append({"role": "user", "content": "You did not use a tool. Please use a tool or use 'finish'."})
            continue
            
        execution_results = []
        finished = False
        final_result = ""
        
        for tc in tool_calls:
            t_name = tc.get("function", {}).get("name", "")
            t_args = tc.get("function", {}).get("arguments", {})
            
            if t_name == "finish":
                finished = True
                final_result = t_args.get("result", "Completed.")
                break
                
            func = getattr(browser_actions, t_name, None)
            if func:
                print(f"[Browser Subagent] Executing: {t_name}({t_args})")
                f = io.StringIO()
                with redirect_stdout(f):
                    try:
                        func(**t_args)
                    except Exception as e:
                        print(f"Tool execution failed: {e}")
                
                out = f.getvalue()
                execution_results.append(f"[Tool: {t_name}] Result:\n{out}")
            else:
                execution_results.append(f"Error: Tool {t_name} not found.")
                
        if finished:
            print(f"[Browser Subagent] Finished: {final_result}")
            return final_result
            
        history.append({"role": "user", "content": "\n".join(execution_results)})
        
    return "Browser Agent stopped after 15 steps without finishing."
