import os
import glob
import time
import base64
import re
from backend import state
from dotenv import load_dotenv
from google import genai
from google.genai import types
from backend.config_paths import ENV_FILE, WORKSPACE_DIR

load_dotenv(ENV_FILE)

# --- Key Rotation Setup ---
raw_keys = os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

if not API_KEYS:
    print("\033[91m[Syntiox CORE] WARNING: No GEMINI_API_KEY found in .env.\033[0m")
else:
    print(f"\033[92m[Syntiox CORE] Loaded {len(API_KEYS)} Gemini API Key(s) for rotation.\033[0m")

current_key_idx = 0
INVALID_API_KEYS = set()
BUSY_RETRY_DELAYS = [5, 10, 15, 15, 15, 15, 15]

# Read model from .env, fallback to gemma-4-31b-it if not set
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemma-4-31b-it")
print(f"\033[92m[Syntiox CORE] Google Model: {GOOGLE_MODEL}\033[0m")

try:
    from groq import Groq
except ImportError:
    Groq = None

# Groq key rotation setup
raw_groq_keys = os.getenv("GROQ_API_KEY", "")
GROQ_API_KEYS = [k.strip() for k in raw_groq_keys.split(",") if k.strip()]
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
current_groq_key_idx = 0

if GROQ_API_KEYS:
    print(f"\033[92m[Syntiox CORE] Loaded {len(GROQ_API_KEYS)} Groq API Key(s) for fast routing/summary.\033[0m")
    print(f"\033[92m[Syntiox CORE] Groq Model: {GROQ_MODEL}\033[0m")

def get_groq_client():
    if not GROQ_API_KEYS or Groq is None:
        return None
    return Groq(api_key=GROQ_API_KEYS[current_groq_key_idx])

def rotate_groq_key():
    global current_groq_key_idx
    if GROQ_API_KEYS:
        current_groq_key_idx = (current_groq_key_idx + 1) % len(GROQ_API_KEYS)
        print(f"\033[93m[System] Rotated to Groq API Key #{current_groq_key_idx + 1}.\033[0m")

def safe_groq_chat(prompt: str, system_prompt: str = None, json_mode: bool = False, max_tokens: int = None) -> str:
    if not GROQ_API_KEYS or Groq is None:
        return None

    max_attempts = len(GROQ_API_KEYS)
    for _ in range(max_attempts):
        try:
            client = get_groq_client()
            if not client:
                return None

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            kwargs = {
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": 0.1
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception:
            rotate_groq_key()
            time.sleep(0.3)
    return None

def get_valid_keys():
    return [k for k in API_KEYS if k not in INVALID_API_KEYS]

def mark_current_key_invalid():
    global current_key_idx
    if API_KEYS and 0 <= current_key_idx < len(API_KEYS):
        bad_key = API_KEYS[current_key_idx]
        if bad_key not in INVALID_API_KEYS:
            INVALID_API_KEYS.add(bad_key)
            print(f"\033[91m[System] API Key #{current_key_idx + 1} is invalid (API_KEY_INVALID). Saved in RAM and skipping permanently.\033[0m")

def get_current_client():
    global current_key_idx
    if API_KEYS:
        if not get_valid_keys():
            raise Exception("All configured Gemini API keys are invalid (API_KEY_INVALID).")
        for _ in range(len(API_KEYS)):
            if API_KEYS[current_key_idx] not in INVALID_API_KEYS:
                break
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
        return genai.Client(api_key=API_KEYS[current_key_idx])
    return genai.Client()

def rotate_key():
    global current_key_idx
    if API_KEYS:
        if not get_valid_keys():
            return
        for _ in range(len(API_KEYS)):
            current_key_idx = (current_key_idx + 1) % len(API_KEYS)
            if API_KEYS[current_key_idx] not in INVALID_API_KEYS:
                print(f"\033[93m[System] Rotated to API Key #{current_key_idx + 1}.\033[0m")
                break

def is_invalid_key_error(error_str: str) -> bool:
    return any(k in error_str for k in (
        "api_key_invalid",
        "api key not valid",
        "api_key_not_valid",
        "invalid api key",
        "api_key_expired",
        "unauthenticated",
    ))

def is_server_busy_error(error_str: str) -> bool:
    return any(k in error_str for k in (
        "503",
        "unavailable",
        "overloaded",
        "high demand",
        "service_unavailable",
        "temporarily unavailable",
        "server is busy",
        "500",
        "internal error",
        "502",
        "bad gateway",
        "504",
        "deadline_exceeded",
        "gateway timeout",
        "disconnected",
        "eof",
    ))

def is_quota_error(error_str: str) -> bool:
    return any(k in error_str for k in (
        "429",
        "quota",
        "exhausted",
        "too many requests",
        "rate_limit",
        "403",
        "permission_denied",
    ))

def safe_generate_content(prompt_or_contents, image_base64=None, stream_callback=None, sys_prompt=None, tools=None, response_schema=None, response_mime_type=None, max_output_tokens=None, retry_on_busy=True):
    """
    Synchronous wrapper with invalid key RAM tracking, 429 key rotation, and 503/busy backoff retries.
    Accepts either a string prompt or a list of formatted types.Content objects.
    """
    last_error = None
    busy_retries = 0
    max_busy_retries = len(BUSY_RETRY_DELAYS)
    quota_attempts = 0
    
    while True:
        try:
            client = get_current_client()
            
            contents = []
            if isinstance(prompt_or_contents, str):
                parts = []
                if image_base64:
                    try:
                        img_data = base64.b64decode(image_base64)
                        parts.append(types.Part.from_bytes(data=img_data, mime_type='image/png'))
                    except Exception as e:
                        print(f"\033[91m[Syntiox CORE] Failed to parse image base64: {e}\033[0m")
                parts.append(types.Part.from_text(text=prompt_or_contents))
                contents.append(types.Content(role="user", parts=parts))
            else:
                contents = prompt_or_contents
            
            config = types.GenerateContentConfig()
            config.temperature = 0.2
            if sys_prompt:
                config.system_instruction = sys_prompt
            if tools:
                config.tools = tools
            if response_mime_type:
                config.response_mime_type = response_mime_type
            if response_schema:
                config.response_schema = response_schema
            if max_output_tokens:
                config.max_output_tokens = max_output_tokens
            
            response_stream = client.models.generate_content_stream(
                model=GOOGLE_MODEL,
                contents=contents,
                config=config
            )
            
            full_response = ""
            function_calls = []
            function_call_parts = []
            raw_response = None
            restored_state = False
            
            for chunk in response_stream:
                raw_response = chunk # Store last chunk for raw access
                if busy_retries > 0 and not restored_state:
                    state.set_ui_state("Thinking")
                    restored_state = True
                if getattr(state, 'STOP_REQUESTED', False):
                    full_response += "\n\n[System: Generation stopped by user]\n<task_complete />"
                    break
                
                # Check for function calls and preserve the raw Part object for thought_signatures
                if getattr(chunk, "candidates", None):
                    for cand in chunk.candidates:
                        if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                            for p in cand.content.parts:
                                if getattr(p, "function_call", None):
                                    function_calls.append(p.function_call)
                                    function_call_parts.append(p)
                                    
                try:
                    text = chunk.text
                except (ValueError, AttributeError):
                    text = None
                if text:
                    full_response += text
                    if stream_callback:
                        stream_callback(text)
                        
            # FALLBACK: If streaming failed/aborted AND no function calls were found
            if not full_response.strip() and not function_calls:
                print("\n\033[93m[Syntiox CORE] Streaming failed or empty. Using Non-Streaming Fallback...\033[0m")
                response = client.models.generate_content(
                    model=GOOGLE_MODEL,
                    contents=contents,
                    config=config
                )
                raw_response = response
                if busy_retries > 0 and not restored_state:
                    state.set_ui_state("Thinking")
                    restored_state = True
                
                if getattr(response, "candidates", None):
                    for cand in response.candidates:
                        if getattr(cand, "content", None) and getattr(cand.content, "parts", None):
                            for p in cand.content.parts:
                                if getattr(p, "function_call", None):
                                    function_calls.append(p.function_call)
                                    function_call_parts.append(p)
                
                try:
                    full_response = response.text or ""
                except ValueError:
                    full_response = ""
                    
                if stream_callback and full_response:
                    for i in range(0, len(full_response), 4):
                        if getattr(state, 'STOP_REQUESTED', False):
                            full_response = full_response[:i] + "\n\n[System: Generation stopped by user]\n<task_complete />"
                            break
                        stream_callback(full_response[i:i+4])
                        time.sleep(0.005)
                        
                if not full_response.strip() and not function_calls:
                    finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "Unknown"
                    if "MALFORMED" in finish_reason or "OTHER" in finish_reason:
                        print(f"\033[93m[System Recovery] Model generated a malformed response ({finish_reason}). Injecting recovery prompt...\033[0m")
                        full_response = "<thought>\n[System Error: The API generated a malformed response and blocked it. This is a Google API backend issue. Please rethink your plan and output your next step differently.]\n[SYSTEM_RECOVERY_REQUIRED]\n</thought>"
                    else:
                        raise Exception(f"API returned an empty response even after fallback. Finish Reason: {finish_reason}")
                        
            return {"content": full_response, "native_function_call_parts": function_call_parts, "raw_response": raw_response}
            
        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            if is_invalid_key_error(error_str):
                mark_current_key_invalid()
                if API_KEYS and not get_valid_keys():
                    raise Exception("All configured Gemini API keys are invalid (API_KEY_INVALID).")
                rotate_key()
                continue

            if is_server_busy_error(error_str):
                if not retry_on_busy:
                    raise e
                busy_retries += 1
                if busy_retries > max_busy_retries:
                    state.set_ui_state("Server Very Busy")
                    raise Exception(f"Server is very busy right now (Model Unavailable after {max_busy_retries}/{max_busy_retries} retries). Please try again later.")

                wait_seconds = BUSY_RETRY_DELAYS[busy_retries - 1]
                rotate_key()
                quota_attempts = 0

                for remaining in range(wait_seconds, 0, -1):
                    if getattr(state, 'STOP_REQUESTED', False):
                        raise Exception("Generation stopped by user.")
                    status_text = f"Model Unavailable - Retrying in {remaining}s ({busy_retries}/{max_busy_retries})"
                    state.set_ui_state(status_text)
                    print(f"\r\033[93m[Syntiox CORE] {status_text}   \033[0m", end="", flush=True)
                    time.sleep(1)
                print()
                state.set_ui_state(f"Model Unavailable - Retrying now ({busy_retries}/{max_busy_retries})")
                continue

            if is_quota_error(error_str):
                quota_attempts += 1
                valid_count = len(get_valid_keys()) if API_KEYS else 1
                if quota_attempts >= max(1, valid_count):
                    raise Exception(f"All {valid_count} valid API keys failed due to quota/rate limits. Last error: {last_error}")
                rotate_key()
                time.sleep(0.5)
                continue

            print(f"\033[91m[API Error - Non Retryable] {e}\033[0m")
            raise e

# --- Skills Loading ---
SKILLS_CACHE = []
ACTIVE_ROUTED_SKILLS = []

def preload_skills():
    global SKILLS_CACHE
    if SKILLS_CACHE:
        return
    from backend.config_paths import SKILLS_DIR
    skills_dir = SKILLS_DIR
    skill_files = glob.glob(os.path.join(skills_dir, "**", "SKILL.md"), recursive=True)
    
    for filepath in skill_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    body = parts[2].strip()
                    keywords_line = next((line for line in frontmatter.split('\n') if line.startswith('keywords:')), None)
                    name_line = next((line for line in frontmatter.split('\n') if line.startswith('name:')), None)
                    desc_line = next((line for line in frontmatter.split('\n') if line.startswith('description:')), None)
                    
                    name = name_line.split('name:')[1].strip() if name_line else "Unknown Skill"
                    description = desc_line.split('description:')[1].strip() if desc_line else ""
                    keywords = [k.strip().lower() for k in keywords_line.split('keywords:')[1].split(',')] if keywords_line else []
                    
                    rel_path = os.path.relpath(filepath, start=skills_dir)
                    rel_path = "skills/" + rel_path.replace("\\", "/")
                    skill_id = os.path.basename(os.path.dirname(filepath)).lower()
                    SKILLS_CACHE.append({
                        "id": skill_id,
                        "path": rel_path,
                        "name": name,
                        "description": description,
                        "keywords": keywords,
                        "body": body
                    })
        except Exception:
            pass
    print(f"Loaded {len(SKILLS_CACHE)} skills into cache.")

def route_skills_and_tools(user_prompt: str, history_str: str = "") -> dict:
    import os
    import ast
    import json
    
    preload_skills()
    skill_descriptions = ""
    if SKILLS_CACHE:
        for skill in SKILLS_CACHE:
            kw = skill.get("keywords", [])
            if "always" in kw or "default" in kw:
                continue
            skill_descriptions += f"- Skill [{skill['id']}] ({skill['name']}): {skill.get('description', '')}\n"

    dynamic_dir = os.path.join(os.path.dirname(__file__), "..", "tools", "dynamic")
    tools_descriptions = ""
    
    if os.path.exists(dynamic_dir):
        packages_dict = {}
        for root, _, files in os.walk(dynamic_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    rel_path = os.path.relpath(os.path.join(root, file), dynamic_dir)
                    path_parts = rel_path.split(os.sep)
                    pkg_name = path_parts[-2] if len(path_parts) > 1 else file[:-3]
                    
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            tree = ast.parse(f.read())
                        funcs = []
                        for node in tree.body:
                            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                                doc = ast.get_docstring(node)
                                doc_short = doc.strip().split('\n')[0] if doc else "No description"
                                funcs.append(f"{node.name}: {doc_short}")
                        if funcs:
                            if pkg_name not in packages_dict:
                                packages_dict[pkg_name] = []
                            packages_dict[pkg_name].extend(funcs)
                    except:
                        pass
                        
        for pkg, funcs in packages_dict.items():
            tools_descriptions += f"- Tool Package [{pkg}]:\n"
            for fn in funcs:
                tools_descriptions += f"    * {fn}\n"

    if not skill_descriptions and not tools_descriptions:
        return {"skills": [], "tools": []}

    prompt = "System: You are a Router for an AI Agent. Core file, terminal, web search, codebase search, and browser tools are already loaded by default. Select the additional skills and dynamic tool packages needed to fulfill the user's request.\n\n"
    if skill_descriptions:
        prompt += f"Available Skills:\n{skill_descriptions}\n"
    if tools_descriptions:
        prompt += f"Available Tool Packages:\n{tools_descriptions}\n"
        
    prompt += f"\nRecent History: {history_str}\nUser Request: {user_prompt}\n\nReply ONLY with a JSON object containing two arrays: 'skills' and 'tools', specifying the exact Skill IDs/names and Tool Package names required. (e.g. {{\"tools\": [\"math_tools\", \"system_tools\"], \"skills\": [\"developer_git\"]}}). If none are needed, reply with empty arrays."
    
    res = safe_groq_chat(prompt, json_mode=True, max_tokens=256)
    if not res:
        try:
            res = safe_generate_content(prompt, response_mime_type="application/json", max_output_tokens=256, retry_on_busy=False)["content"].strip()
        except Exception:
            res = None

    if res:
        try:
            selected = json.loads(res.strip())
            result = {"skills": [], "tools": []}
            if isinstance(selected, dict):
                if "skills" in selected and isinstance(selected["skills"], list):
                    result["skills"] = [str(s).strip().strip("[]\"'").lower() for s in selected["skills"]]
                if "tools" in selected and isinstance(selected["tools"], list):
                    result["tools"] = [str(s).strip().strip("[]\"'").lower() for s in selected["tools"]]
            return result
        except Exception:
            pass
    return {"skills": [], "tools": []}

def load_dynamic_skills(user_prompt: str, step: int = 1, history_str: str = "") -> str:
    global ACTIVE_ROUTED_SKILLS
    preload_skills()
    skill_contents = []
    
    if step == 1:
        print(f"\033[95m[Syntiox CORE] Routing Skills and Tools dynamically...\033[0m")
        ACTIVE_ROUTED_SKILLS = route_skills_and_tools(user_prompt, history_str)
        
        has_items = ACTIVE_ROUTED_SKILLS.get("skills") or ACTIVE_ROUTED_SKILLS.get("tools")
        if has_items:
            combined_names = ACTIVE_ROUTED_SKILLS.get("skills", []) + ACTIVE_ROUTED_SKILLS.get("tools", [])
            print(f"\033[96m[Syntiox CORE] Router selected: {', '.join(combined_names)}\033[0m")
        else:
            print(f"\033[96m[Syntiox CORE] Router selected no external skills or tools.\033[0m")
    
    routed_skills = ACTIVE_ROUTED_SKILLS.get("skills", [])
    for skill in SKILLS_CACHE:
        should_load = False
        kw = skill.get("keywords", [])
        skill_name = skill.get("name", "").lower()
        skill_id = skill.get("id", "")
        
        if "always" in kw or "default" in kw:
            should_load = True
        elif skill_name in routed_skills or skill_id in routed_skills:
            should_load = True
            
        if should_load:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")).replace('\\', '\\\\')
            body_with_paths = skill["body"].replace("{ROOT_DIR}", root_dir)
            skill_contents.append(body_with_paths)
            if step == 1:
                print(f"\033[96m[Syntiox CORE] Activating Skill: {skill['path']}\033[0m")
            
    if not skill_contents:
        return "You are Syntiox CORE, an autonomous On-Demand Local OS Agent."
        
    return "\n\n".join(skill_contents)

def summarize_memory(chat_history_list: list) -> list:
    if len(chat_history_list) <= 6:
        return chat_history_list
        
    recent_turns = chat_history_list[-3:]
    old_turns = chat_history_list[:-3]
    old_history_str = "\n".join(old_turns)
    
    sys_prompt = "You are an AI assistant. Please write a highly concise summary of the following past conversation so we don't forget the context. Keep important facts, exact file paths, completed actions, and pending goals. Output only the summary."
    groq_summary = safe_groq_chat(old_history_str, system_prompt=sys_prompt, max_tokens=512)
    if groq_summary and groq_summary.strip():
        new_history = [f"[System: Summary of older conversation] {groq_summary.strip()}"] + recent_turns
        return new_history

    prompt = f"System: {sys_prompt}\n\nConversation to summarize:\n{old_history_str}"
    try:
        response = safe_generate_content(prompt, retry_on_busy=False)
        summary = response["content"].strip()
        new_history = [f"[System: Summary of older conversation] {summary}"] + recent_turns
        return new_history
    except Exception:
        return chat_history_list[-6:]

def classify_intent(user_prompt: str, manual_override: str = None, history_str: str = "") -> str:
    if manual_override and manual_override.upper() in ["CHAT", "AGENT"]:
        return manual_override.upper()
        
    prompt = f"System: You are an intent classifier. Respond with EXACTLY 'CHAT' or 'AGENT'.\n- If the user wants you to do something on their computer, write code, run commands, inspect local files/paths, execute a plan, search the web, do a math calculation, run python code, or use a tool, you MUST classify it as 'AGENT'.\n- CRITICAL: If the user prompt contains Sinhala action verbs like 'කරන්න' (do), 'හදන්න' (make/create), 'ලියන්න' (write), 'බලන්න' (look/view), 'පෙන්නන්න' (show), 'රන් කරන්න' (run), or 'හොයන්න' (find/search), you MUST classify it as 'AGENT'.\n- ALSO, if the user asks ANY factual question, asks about a person, event, movie, or anything that requires internet/up-to-date knowledge (e.g., 'who is X?', 'what is Y?', 'best movies', 'search for x'), or is replying to continue/confirm a previous agent task, you MUST say 'AGENT'.\n- If they are ONLY greeting you (e.g., 'hello', 'how are you') or making casual conversational remarks that require absolutely no research or tools, say 'CHAT'.\n\nRecent Chat History:\n{history_str}\n\nUser Input: {user_prompt}"
    groq_res = safe_groq_chat(prompt, max_tokens=128)
    if groq_res and groq_res.strip():
        if "AGENT" in groq_res.strip().upper():
            return "AGENT"
        return "CHAT"

    try:
        response = safe_generate_content(prompt, max_output_tokens=16, retry_on_busy=False)
        content = response["content"].strip().upper()
        if "AGENT" in content:
            return "AGENT"
        return "CHAT"
    except Exception as e:
        return "AGENT"

def generate_session_title(user_prompt: str) -> str:
    sys_prompt = "You are a title generator. Generate a very short (2-5 words) title for this conversation based on the user's first prompt. Do not use quotes or prefixes, just output the plain title."
    groq_title = safe_groq_chat(user_prompt, system_prompt=sys_prompt, max_tokens=256)
    if groq_title and groq_title.strip():
        return groq_title.strip().strip('"\'')

    prompt = f"System: {sys_prompt}\n\nUser Input: {user_prompt}"
    try:
        response = safe_generate_content(prompt, max_output_tokens=32, retry_on_busy=False)
        title = response["content"].strip().strip('"\'')
        return title
    except Exception:
        return "Untitled Session"

def load_global_rules() -> str:
    try:
        from backend.config_paths import CONFIG_DIR
        rules_path = os.path.join(CONFIG_DIR, "prompts", "SYNTIOX_CORE.md")

        if os.path.exists(rules_path):
            with open(rules_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                rules_text = "".join(lines[:500])
                if rules_text.strip():
                    return f"\n\n[USER GLOBAL RULES]\nYou MUST follow these user-defined global rules at all times:\n{rules_text}\n[/USER GLOBAL RULES]\n"
    except Exception:
        pass
    return ""

def _get_ui_instruction() -> str:
    ui_mode = os.getenv("LAUNCH_UI", "terminal")
    if ui_mode == "web":
        return "\n[SYSTEM INSTRUCTION: The user is using a modern rich Web UI. Always format your responses beautifully using rich Markdown, including headers, tables, bold text, and code blocks. If there are mathematical equations, format them strictly in LaTeX for MathJax rendering.]\n"
    return "\n[SYSTEM INSTRUCTION: The user is using a plain Terminal CLI. Strictly avoid using complex markdown tables, LaTeX math, or heavy formatting. Use simple plain text, bullet points, and basic spacing so it renders cleanly in a standard terminal shell.]\n"

def generate_chat_response(user_prompt: str, history_str: str = "", image_base64: str = None, stream_callback=None) -> str:
    walkthrough_context = ""
    from backend.session_manager import get_active_brain_path
    brain_path = get_active_brain_path()
    walkthrough_path = os.path.join(brain_path, "walkthrough.md") if brain_path and os.path.exists(os.path.join(brain_path, "walkthrough.md")) else os.path.join(WORKSPACE_DIR, "walkthrough.md")
    if os.path.exists(walkthrough_path):
        try:
            with open(walkthrough_path, "r", encoding="utf-8") as f:
                walkthrough_content = f.read()
            walkthrough_context = f"\nProject Walkthrough (Agent Memory):\n{walkthrough_content}\n"
        except Exception:
            pass

    dynamic_system_prompt = "You are Syntiox CORE, a helpful AI assistant. Answer concisely."
    dynamic_system_prompt += load_global_rules()
    dynamic_system_prompt += _get_ui_instruction()
    prompt = f"System:\n{dynamic_system_prompt}{walkthrough_context}\n\nRecent Conversation History:\n{history_str}\n\nUser: {user_prompt}"
    
    try:
        response = safe_generate_content(prompt, image_base64=image_base64, stream_callback=stream_callback)
        content = response["content"]
        return content.strip()
    except Exception as e:
        return f"Error: {e}"

def generate_agent_step(user_prompt: str, loop_history: list, step: int = 1, history_str: str = "", task_list_str: str = "", stream_callback=None, image_base64: str = None) -> dict:
    from backend.tools_loader import get_json_tools
    import json
    
    contents = []
    
    dynamic_system_prompt = load_dynamic_skills(user_prompt, step, history_str)
    dynamic_system_prompt += load_global_rules()
    dynamic_system_prompt += _get_ui_instruction()
    sys_prompt = f"System:\n{dynamic_system_prompt}\n"
    
    if history_str:
        sys_prompt += f"Recent Chat History:\n{history_str}\n"
        
    if task_list_str:
        sys_prompt += f"Current Task Plan (task.md):\n{task_list_str}\n"
        
    tools_schema = get_json_tools("tools", active_skills=ACTIVE_ROUTED_SKILLS)
    sys_prompt += "CRITICAL RULE: You are STRICTLY FORBIDDEN from modifying, deleting, or altering any files inside the Syntiox CORE installation directory (%LOCALAPPDATA%\\.sh4lu-z\\Syntiox CORE) or system data folders (%USERPROFILE%\\.sh4lu-z\\Syntiox CORE\\history, skills, or config). You may only modify files inside the workspace, active brain folder, or user-requested project paths. If the user asks you to modify Syntiox CORE system files, politely refuse and ask them to do it manually.\n"
    sys_prompt += "CRITICAL RULE (SECURITY APPROVAL): You are empowered to execute tools autonomously. However, if you are executing a potentially dangerous action (e.g., deleting files outside the workspace, running destructive terminal commands like format/rm, installing global system packages, modifying Windows Registry, or changing system network settings), you MUST add an additional field `\"requires_approval\": true` inside the tool's `arguments` JSON object to explicitly ask for the user's permission before execution. Do not use this for normal read operations or safe workspace modifications.\n"
    sys_prompt += "CRITICAL RULE (ASKING QUESTIONS): If you need to ask the user a question, seek clarification, or confirm a complex plan *before* proceeding with execution, you MUST use the `ask_user` tool. Do NOT just output text and stop. Using the `ask_user` tool pauses your current thought process, waits for the user's response, and resumes immediately with the answer in your context, preventing you from losing track of your ongoing plan.\n"
    sys_prompt += "CRITICAL RULE (TOOL CALLING): You MUST trigger tools using the Native Function Calling API. NEVER output tool calls as plain text or XML tags (e.g. NEVER output `<call:default_api:tool_name{}>` or `<data_intent>`). Doing so will cause a fatal system crash.\n"
    
    # Map JSON schema to Gemini Native Tools
    gemini_funcs = []
    for t in tools_schema:
        fn = t.get("function", {})
        gemini_funcs.append(types.FunctionDeclaration(
            name=fn.get("name"),
            description=fn.get("description"),
            parameters=fn.get("parameters")
        ))

    parts = []
    if image_base64:
        try:
            img_data = base64.b64decode(image_base64)
            parts.append(types.Part.from_bytes(data=img_data, mime_type='image/png'))
        except Exception as e:
            pass
            
    parts.append(types.Part.from_text(text=f"User Request: {user_prompt}"))
    contents.append(types.Content(role="user", parts=parts))
    
    recent_steps = loop_history
    if len(loop_history) > 5:
        old_steps = loop_history[:-5]
        recent_steps = loop_history[-5:]
        
        summary_text = "[System Note: Older steps are summarized to save memory. You DO NOT have the exact code/contents from these older steps anymore. BEFORE writing dependent code, you MUST use tools to read the required files again to avoid hallucinating!]\n\n"
        for old_item in old_steps:
            step_num = old_item.get("step")
            thought = old_item.get("thought", "").replace("\n", " ")
            tools = [tc["function"]["name"] for tc in old_item.get("tool_calls", [])]
            exec_res = str(old_item.get("execution_result", "")).replace("\n", " ").strip()
            summary_text += f"- Step {step_num}: Thought: '{thought[:150]}...'. Tools: {', '.join(tools)}. Result: '{exec_res[:150]}...'\n"
            
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=summary_text)]
        ))

    for item in recent_steps:
        if item.get("tool_calls"):
            # Build model turn: optional thought text + native function call parts
            model_parts = []
            thought_text = item.get("thought", "")
            if thought_text and thought_text.strip():
                model_parts.append(types.Part.from_text(text=thought_text))
            
            for tc in item["tool_calls"]:
                fn_name = tc["function"]["name"]
                fn_args = tc["function"]["arguments"]
                if fn_name in ["system_recovery", "system_continue"]:
                    model_parts.append(types.Part.from_text(text=f"[Internal System Task]: {fn_name}"))
                    continue
                try:
                    p = types.Part(function_call=types.FunctionCall(
                        name=fn_name, args=fn_args
                    ))
                    if tc.get("thought_signature"):
                        p.thought_signature = tc.get("thought_signature")
                    model_parts.append(p)
                except Exception:
                    model_parts.append(types.Part.from_text(text=f"Called tool: {fn_name}"))
            
            if not model_parts:
                model_parts.append(types.Part.from_text(text="Executing tool."))
            
            contents.append(types.Content(role="model", parts=model_parts))
            
            # Build function response turn with proper FunctionResponse parts
            exec_result = item.get('execution_result', 'No result.')
            response_parts = []
            for tc in item["tool_calls"]:
                fn_name = tc["function"]["name"]
                if fn_name == "system_recovery":
                    response_parts.append(types.Part.from_text(
                        text=f"[SYSTEM NOTIFICATION]: {str(exec_result)[:4000]}"
                    ))
                    continue
                elif fn_name == "system_continue":
                    response_parts.append(types.Part.from_text(
                        text=f"[SYSTEM NOTIFICATION]: {str(exec_result)[:4000]}"
                    ))
                    continue
                    
                try:
                    response_parts.append(types.Part(function_response=types.FunctionResponse(
                        name=fn_name, response={"result": str(exec_result)[:12000]}
                    )))
                except Exception:
                    response_parts.append(types.Part.from_text(
                        text=f"[Tool {fn_name} result]: {str(exec_result)[:12000]}"
                    ))
            if response_parts:
                contents.append(types.Content(role="user", parts=response_parts))
        else:
            msg = item.get("final_message", "")
            if msg and msg.strip():
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=msg)]
                ))
            
    if contents and contents[-1].role == "model":
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text="Please proceed with the next step or provide your final response.")]
        ))
    
    try:
        response_dict = safe_generate_content(
            contents, 
            stream_callback=stream_callback, 
            sys_prompt=sys_prompt, 
            tools=[types.Tool(function_declarations=gemini_funcs)],
            max_output_tokens=8192
        )
        
        content = response_dict.get("content", "")
        native_call_parts = response_dict.get("native_function_call_parts", [])
        
        # --- PARSE NATIVE TOOL CALLS ---
        tool_calls = []
        if native_call_parts:
            for p in native_call_parts:
                call = p.function_call
                args_dict = {}
                if getattr(call, 'args', None):
                    # args is usually a Map/Dict struct in python SDK
                    args_dict = dict(call.args)
                tool_calls.append({
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": args_dict
                    },
                    "thought_signature": getattr(p, 'thought_signature', None)
                })
                
        # Fallback to parse text-based tool calls if native tools failed to capture them
        if not tool_calls and content and "<call:" in content:
            import re
            import json
            matches = re.findall(r'<call:(?:[a-zA-Z0-9_]+:)?([a-zA-Z0-9_]+)\{(.*?)\}>?', content)
            for name, raw_args in matches:
                args_dict = {}
                try:
                    args_dict = json.loads('{' + raw_args + '}')
                except Exception:
                    for pair in raw_args.split(','):
                        if ':' in pair:
                            k, v = pair.split(':', 1)
                            args_dict[k.strip().strip('"\'')] = v.strip().strip('"\'')
                tool_calls.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": args_dict
                    },
                    "thought_signature": None
                })
        
        status = "CONTINUE" if tool_calls else "COMPLETE"
        
        return {
            "thought": content,
            "tool_calls": tool_calls,
            "status": status,
            "final_message": content if status == "COMPLETE" else "",
            "raw": str(response_dict.get("raw_response"))
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Error communicating with Gemini: {str(e)}"}
