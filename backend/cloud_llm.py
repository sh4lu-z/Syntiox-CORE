import os
import glob
import time
import base64
import re
from backend import state
from dotenv import load_dotenv
from google import genai
from google.genai import types
from backend import state
from backend.config_paths import ENV_FILE, WORKSPACE_DIR

# .env ෆයිල් එක ලෝඩ් කරමු
load_dotenv(ENV_FILE)

# --- Key Rotation Setup ---
raw_keys = os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

if not API_KEYS:
    print("\033[91m[Syntiox CORE] WARNING: No GEMINI_API_KEY found in .env.\033[0m")
else:
    print(f"\033[92m[Syntiox CORE] Loaded {len(API_KEYS)} Gemini API Key(s) for rotation.\033[0m")

current_key_idx = 0

# Read model from .env, fallback to gemma-4-31b-it if not set
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemma-4-31b-it")
print(f"\033[92m[Syntiox CORE] Google Model: {GOOGLE_MODEL}\033[0m")

def get_current_client():
    if API_KEYS:
        return genai.Client(api_key=API_KEYS[current_key_idx])
    return genai.Client()

def rotate_key():
    global current_key_idx
    if API_KEYS:
        current_key_idx = (current_key_idx + 1) % len(API_KEYS)
        print(f"\033[93m[System] Rotated to API Key #{current_key_idx + 1} to avoid rate limits.\033[0m")


def safe_generate_content(prompt_or_contents, image_base64=None, stream_callback=None, sys_prompt=None):
    """
    Synchronous wrapper with retry logic for 429/Quota errors and key rotation.
    Accepts either a string prompt or a list of formatted types.Content objects.
    """
    max_attempts = len(API_KEYS) if API_KEYS else 1
    last_error = None
    
    for attempt in range(max_attempts):
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
            
            response_stream = client.models.generate_content_stream(
                model=GOOGLE_MODEL,
                contents=contents,
                config=config
            )
            
            full_response = ""
            for chunk in response_stream:
                if getattr(state, 'STOP_REQUESTED', False):
                    full_response += "\n\n[System: Generation stopped by user]\n[TASK_COMPLETE]"
                    break
                if chunk.text:
                    full_response += chunk.text
                    if stream_callback:
                        stream_callback(chunk.text)
                        
            # FALLBACK: If streaming failed/aborted (e.g., MALFORMED_RESPONSE SDK bug)
            if not full_response.strip():
                print("\n\033[93m[Syntiox CORE] Streaming failed. Using Non-Streaming Fallback...\033[0m")
                response = client.models.generate_content(
                    model=GOOGLE_MODEL,
                    contents=contents,
                    config=config
                )
                
                try:
                    full_response = response.text or ""
                except ValueError:
                    full_response = ""
                    
                if stream_callback and full_response:
                    for i in range(0, len(full_response), 4):
                        if getattr(state, 'STOP_REQUESTED', False):
                            full_response = full_response[:i] + "\n\n[System: Generation stopped by user]\n[TASK_COMPLETE]"
                            break
                        stream_callback(full_response[i:i+4])
                        time.sleep(0.005)
                        
                if not full_response.strip():
                    finish_reason = str(response.candidates[0].finish_reason) if response.candidates else "Unknown"
                    if "MALFORMED" in finish_reason or "OTHER" in finish_reason:
                        print(f"\033[93m[System Recovery] Model generated a malformed response ({finish_reason}). Injecting recovery prompt...\033[0m")
                        full_response = "<thought>\n[System Error: The API generated a malformed response and blocked it. This is a Google API backend issue. Please rethink your plan and output your next step differently using strictly valid XML.]\n[NEXT_STEP_REQUIRED]\n</thought>"
                    else:
                        raise Exception(f"API returned an empty response even after fallback. Finish Reason: {finish_reason}")
                        
            return {"content": full_response, "tool_calls": [], "raw_response": None}
            
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str or "too many requests" in error_str or "403" in error_str or "503" in error_str or "unavailable" in error_str:
                rotate_key()
                time.sleep(0.5)
            else:
                print(f"\033[91m[API Error - Non Retryable] {e}\033[0m")
                raise e

    raise Exception(f"All {max_attempts} API keys failed. Last error: {last_error}")

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
                    
                    rel_path = os.path.relpath(filepath, start=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    rel_path = rel_path.replace("\\", "/")
                    SKILLS_CACHE.append({
                        "path": rel_path,
                        "name": name,
                        "description": description,
                        "keywords": keywords,
                        "body": body
                    })
        except:
            pass
    print(f"Loaded {len(SKILLS_CACHE)} skills into cache.")

def route_skills(user_prompt: str, history_str: str = "") -> list:
    if not SKILLS_CACHE:
        return []
        
    skill_descriptions = ""
    for skill in SKILLS_CACHE:
        kw = skill.get("keywords", [])
        if "always" in kw or "default" in kw:
            continue
        skill_descriptions += f"- {skill['name']}: {skill.get('description', '')}\n"
        
    prompt = f"System: You are a Skill Router for an AI Agent. Your job is to select the most appropriate skills needed to fulfill the user's request.\n\nAvailable Skills:\n{skill_descriptions}\n\nRecent Chat History:\n{history_str}\n\nUser Request: {user_prompt}\n\nReply ONLY with a comma-separated list of the exact Skill names required. If no skills are needed, reply with NONE."
    
    try:
        response = safe_generate_content(prompt)
        content = response["content"].strip()
        if content.upper() == "NONE":
            return []
        return [s.strip().lower() for s in content.split(",")]
    except:
        return []

def load_dynamic_skills(user_prompt: str, step: int = 1, history_str: str = "") -> str:
    global ACTIVE_ROUTED_SKILLS
    preload_skills()
    skill_contents = []
    
    if step == 1:
        print(f"\033[95m[Syntiox CORE] Routing Skills dynamically based on intent...\033[0m")
        ACTIVE_ROUTED_SKILLS = route_skills(user_prompt, history_str)
        if ACTIVE_ROUTED_SKILLS:
            print(f"\033[96m[Syntiox CORE] Router selected: {', '.join(ACTIVE_ROUTED_SKILLS)}\033[0m")
        else:
            print(f"\033[96m[Syntiox CORE] Router selected no external skills.\033[0m")
    
    for skill in SKILLS_CACHE:
        should_load = False
        kw = skill.get("keywords", [])
        
        if "always" in kw or "default" in kw:
            should_load = True
        elif skill.get("name", "").lower() in ACTIVE_ROUTED_SKILLS:
            should_load = True
            
        if should_load:
            skill_contents.append(skill["body"])
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
    
    prompt = f"System: You are an AI assistant. Please write a highly concise summary of the following past conversation so we don't forget the context. Keep important facts, paths, and goals. Output only the summary.\n\nConversation to summarize:\n{old_history_str}"
    
    try:
        response = safe_generate_content(prompt)
        summary = response["content"].strip()
        new_history = [f"[System: Summary of older conversation] {summary}"] + recent_turns
        return new_history
    except:
        return chat_history_list[-6:]


def classify_intent(user_prompt: str, manual_override: str = None, history_str: str = "") -> str:
    if manual_override and manual_override.upper() in ["CHAT", "AGENT"]:
        return manual_override.upper()
        
    prompt = f"System: You are an intent classifier. Respond with EXACTLY 'CHAT' or 'AGENT'.\n- If the user wants you to do something on their computer, write code, run commands, inspect local files/paths, execute a plan, search the web, do a math calculation, run python code, or use a tool. \n- CRITICAL: If the user prompt contains Sinhala action verbs like 'කරන්න' (do), 'හදන්න' (make/create), 'ලියන්න' (write), 'බලන්න' (look/view), 'පෙන්නන්න' (show), 'රන් කරන්න' (run), or 'හොයන්න' (find/search), you MUST classify it as 'AGENT'.\n- ALSO, if the user asks ANY factual question, asks about a person, event, movie, or anything that requires internet/up-to-date knowledge (e.g., 'who is X?', 'what is Y?', 'best movies', 'search for x'), you MUST say 'AGENT' so it can use the web search tool.\n- If they are ONLY greeting you (e.g., 'hello', 'how are you') or making casual conversational remarks that require absolutely no research or tools, say 'CHAT'.\n\nRecent Chat History:\n{history_str}\n\nUser Input: {user_prompt}"
    try:
        response = safe_generate_content(prompt)
        content = response["content"].strip().upper()
        if "AGENT" in content:
            return "AGENT"
        return "CHAT"
    except Exception as e:
        return "AGENT"

def generate_session_title(user_prompt: str) -> str:
    prompt = f"System: You are a title generator. Generate a very short (2-5 words) title for this conversation based on the user's first prompt. Do not use quotes or prefixes, just the title.\n\nUser Input: {user_prompt}"
    try:
        response = safe_generate_content(prompt)
        title = response["content"].strip()
        return title
    except:
        return "Untitled Session"


def generate_chat_response(user_prompt: str, history_str: str = "", image_base64: str = None, stream_callback=None) -> str:
    walkthrough_context = ""
    walkthrough_path = os.path.join(WORKSPACE_DIR, "walkthrough.md")
    if os.path.exists(walkthrough_path):
        try:
            with open(walkthrough_path, "r", encoding="utf-8") as f:
                walkthrough_content = f.read()
            walkthrough_context = f"\nProject Walkthrough (Agent Memory):\n{walkthrough_content}\n"
        except:
            pass

    dynamic_system_prompt = "You are Syntiox CORE, a helpful AI assistant. Answer concisely."
    prompt = f"System:\n{dynamic_system_prompt}{walkthrough_context}\n\nRecent Conversation History:\n{history_str}\n\nUser: {user_prompt}"
    
    try:
        response = safe_generate_content(prompt, image_base64=image_base64, stream_callback=stream_callback)
        content = response["content"]
        content = re.sub(r'<\|?channel\|?>thought.*?<channel\|?>', '', content, flags=re.DOTALL)
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL)
        return content.strip()
    except Exception as e:
        return f"Error: {e}"


def generate_agent_step(user_prompt: str, loop_history: list, step: int = 1, history_str: str = "", task_list_str: str = "", stream_callback=None, image_base64: str = None) -> dict:
    from backend.tools_loader import get_json_tools
    from backend.parser import extract_tool_calls
    import json
    
    contents = []
    
    dynamic_system_prompt = load_dynamic_skills(user_prompt, step, history_str)
    sys_prompt = f"System:\n{dynamic_system_prompt}\n"
    
    if history_str:
        sys_prompt += f"Recent Chat History:\n{history_str}\n"
        
    if task_list_str:
        sys_prompt += f"Current Task Plan (task.md):\n{task_list_str}\n"
        
    tools_schema = get_json_tools("TOOLS")
    sys_prompt += "\n\nYou have access to the following TOOLS. If you need to perform an action, you MUST output a Tool Call using this EXACT XML tag enclosing a JSON payload:\n"
    sys_prompt += "<tool_call>{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"value\"}}</tool_call>\n"
    sys_prompt += "Example: <tool_call>{\"name\": \"run_terminal_command\", \"arguments\": {\"command\": \"dir\"}}</tool_call>\n"
    sys_prompt += "CRITICAL RULE: DO NOT ATTEMPT TO USE NATIVE GOOGLE API FUNCTION CALLS. NEVER use 'call:tool_name' syntax. You must ONLY output plain text with the <tool_call> XML tag.\n"
    sys_prompt += "CRITICAL RULE: If you are explaining tool usage to the user, DO NOT use the raw <tool_call> tags. You MUST wrap them in markdown backticks (```). Only use raw unescaped tags when you ACTUALLY want to execute the tool.\n"
    sys_prompt += "CRITICAL: NEVER use LaTeX (like \\mathrm), markdown, or any text formatting inside the JSON braces. It must be valid, raw JSON.\n"
    sys_prompt += "CRITICAL: When writing Windows file paths inside JSON, you MUST double-escape backslashes (e.g. C:\\\\Users\\\\Desktop). DO NOT use single backslashes.\n"
    sys_prompt += "You can output multiple tools consecutively to run them concurrently.\n\nAVAILABLE TOOLS:\n"
    sys_prompt += json.dumps(tools_schema, indent=2) + "\n\n"
    sys_prompt += "If you are just talking to the user and don't need tools, output standard text."

    # Update config to use native system_instruction
    config = types.GenerateContentConfig()
    config.system_instruction = sys_prompt
    # Increase temp slightly to prevent safety loop blocks
    config.temperature = 0.1

    parts = []
    if image_base64:
        try:
            img_data = base64.b64decode(image_base64)
            parts.append(types.Part.from_bytes(data=img_data, mime_type='image/png'))
        except Exception as e:
            pass
            
    parts.append(types.Part.from_text(text=f"User Request: {user_prompt}"))
    contents.append(types.Content(role="user", parts=parts))
    
    for item in loop_history:
        if item.get("tool_calls"):
            contents.append(types.Content(
                role="model", 
                parts=[types.Part.from_text(text=item.get("thought", "Executed tool."))]
            ))
            tool_names = ", ".join([tc["function"]["name"] for tc in item["tool_calls"]])
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"[System] Tools [{tool_names}] executed. Results:\n{item.get('execution_result')}")]
            ))
        else:
            contents.append(types.Content(
                role="model",
                parts=[types.Part.from_text(text=item.get("final_message", ""))]
            ))
            
    if contents and contents[-1].role == "model":
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text="Please proceed with the next step or provide your final response.")]
        ))
    
    try:
        response_dict = safe_generate_content(contents, stream_callback=stream_callback, sys_prompt=sys_prompt)
        
        content = response_dict.get("content", "")
        
        # --- PARSE TOOL CALLS MANUALLY ---
        tool_calls = extract_tool_calls(content)
        
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
