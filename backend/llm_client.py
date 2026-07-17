import os
import glob
import time
import base64
import re
from backend import state
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# --- Key Rotation Setup ---
raw_keys = os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in raw_keys.split(",") if k.strip()]

if not API_KEYS:
    print("\033[91m[Syntiox CORE] WARNING: No GEMINI_API_KEY found in .env.\033[0m")
else:
    print(f"\033[92m[Syntiox CORE] Loaded {len(API_KEYS)} Gemini API Key(s) for rotation.\033[0m")

current_key_idx = 0

def get_current_client():
    if API_KEYS:
        return genai.Client(api_key=API_KEYS[current_key_idx])
    return genai.Client()

def rotate_key():
    global current_key_idx
    if API_KEYS:
        current_key_idx = (current_key_idx + 1) % len(API_KEYS)
        print(f"\033[93m[System] Rotated to API Key #{current_key_idx + 1} to avoid rate limits.\033[0m")


def safe_generate_content(prompt, image_base64=None, stream_callback=None):
    """
    Synchronous wrapper with retry logic for 429/Quota errors and key rotation.
    """
    max_attempts = len(API_KEYS) if API_KEYS else 1
    last_error = None
    
    for attempt in range(max_attempts):
        try:
            client = get_current_client()
            
            # Setup Vision capabilities if image is provided
            contents = []
            if image_base64:
                try:
                    img_data = base64.b64decode(image_base64)
                    contents.append(types.Part.from_bytes(data=img_data, mime_type='image/png'))
                except Exception as e:
                    print(f"\033[91m[Syntiox CORE] Failed to parse image base64: {e}\033[0m")
            
            contents.append(prompt)
            
            # Use streaming
            response_stream = client.models.generate_content_stream(
                model="gemma-4-31b-it",
                contents=contents
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
                        
            return full_response
            
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str or "too many requests" in error_str or "403" in error_str or "503" in error_str or "unavailable" in error_str:
                rotate_key()
                time.sleep(0.5)
            else:
                print(f"\033[91m[API Error] {e} - Attempting rotation...\033[0m")
                rotate_key()
                time.sleep(0.5)

    raise Exception(f"All {max_attempts} API keys failed. Last error: {last_error}")


# --- Skills Loading ---
SKILLS_CACHE = []
ACTIVE_ROUTED_SKILLS = []

def preload_skills():
    global SKILLS_CACHE
    if SKILLS_CACHE:
        return
    skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SKILLS")
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

def route_skills(user_prompt: str) -> list:
    if not SKILLS_CACHE:
        return []
        
    skill_descriptions = ""
    for skill in SKILLS_CACHE:
        kw = skill.get("keywords", [])
        if "always" in kw or "default" in kw:
            continue
        skill_descriptions += f"- {skill['name']}: {skill.get('description', '')}\n"
        
    prompt = f"System: You are a Skill Router for an AI Agent. Your job is to select the most appropriate skills needed to fulfill the user's request.\n\nAvailable Skills:\n{skill_descriptions}\n\nUser Request: {user_prompt}\n\nReply ONLY with a comma-separated list of the exact Skill names required. If no skills are needed, reply with NONE."
    
    try:
        content = safe_generate_content(prompt).strip()
        if content.upper() == "NONE":
            return []
        return [s.strip().lower() for s in content.split(",")]
    except:
        return []

def load_dynamic_skills(user_prompt: str, step: int = 1) -> str:
    global ACTIVE_ROUTED_SKILLS
    preload_skills()
    skill_contents = []
    
    if step == 1:
        print(f"\033[95m[Syntiox CORE] Routing Skills dynamically based on intent...\033[0m")
        ACTIVE_ROUTED_SKILLS = route_skills(user_prompt)
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
        summary = safe_generate_content(prompt).strip()
        new_history = [f"[System: Summary of older conversation] {summary}"] + recent_turns
        return new_history
    except:
        return chat_history_list[-6:]


def classify_intent(user_prompt: str) -> str:
    prompt = f"System: You are an intent classifier. Respond with EXACTLY 'CHAT' or 'AGENT'.\n- If the user wants you to do something on their computer, write code, run commands, inspect local files/paths, execute a plan, search the web, do a math calculation, run python code, or use a tool. ALSO, if the user asks ANY factual question, asks about a person, event, movie, or anything that requires internet/up-to-date knowledge (e.g., 'who is X?', 'what is Y?', 'best movies', 'search for x'), you MUST say 'AGENT' so it can use the web search tool.\n- If they are ONLY greeting you (e.g., 'hello', 'how are you') or making casual conversational remarks that require absolutely no research or tools, say 'CHAT'.\n\nUser Input: {user_prompt}"
    try:
        content = safe_generate_content(prompt).strip().upper()
        if "AGENT" in content:
            return "AGENT"
        return "CHAT"
    except Exception as e:
        return "AGENT"

def generate_session_title(user_prompt: str) -> str:
    prompt = f"System: You are a title generator. Generate a very short (2-5 words) title for this conversation based on the user's first prompt. Do not use quotes or prefixes, just the title.\n\nUser Input: {user_prompt}"
    try:
        title = safe_generate_content(prompt).strip()
        return title
    except:
        return "Untitled Session"


def generate_chat_response(user_prompt: str, history_str: str = "", image_base64: str = None, stream_callback=None) -> str:
    walkthrough_context = ""
    walkthrough_path = os.path.join("workspace", "walkthrough.md")
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
        content = safe_generate_content(prompt, image_base64=image_base64, stream_callback=stream_callback)
        content = re.sub(r'<\|?channel\|?>thought.*?<channel\|?>', '', content, flags=re.DOTALL)
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL)
        return content.strip()
    except Exception as e:
        return f"Error: {e}"


def generate_agent_step(user_prompt: str, scratchpad: str, execution_result: str, image_base64: str = None, step: int = 1, history_str: str = "", task_list_str: str = "", stream_callback=None) -> dict:
    prompt_text = ""
    if history_str:
        prompt_text += f"Recent Conversation History:\n{history_str}\n\n"
        
    prompt_text += f"Current User Task: {user_prompt}\n"
    
    if task_list_str:
        prompt_text += f"\nCurrent Task Plan (task.md):\n{task_list_str}\n"
        prompt_text += "CRITICAL INSTRUCTION: Find the first incomplete task `[ ]` in the plan above. Your goal is to execute it. In the SAME Python script that executes the task, you MUST also write code to read `task.md`, use simple string replacement (`content.replace`) to replace that specific `[ ]` with `[x]`, and overwrite the file. DO NOT use the `re` module for this to avoid path escape errors. Do this simultaneously.\n"
    else:
        prompt_text += "CRITICAL INSTRUCTION: You do not have a plan yet. If the user's request requires multiple distinct steps, your FIRST action MUST be to create a `task.md` file containing a checklist of steps using `[ ]`. Write a python script to save this file, then output [NEXT_STEP_REQUIRED].\n"
    
    if scratchpad:
        prompt_text += f"\nPrevious Scratchpad:\n{scratchpad}\n"
    if execution_result:
        prompt_text += f"\nLast Execution Result/Error:\n{execution_result}\n"
        
    prompt_text += "\nBased on the history and previous results, generate the next step. Your thoughts should naturally precede your actions."
    prompt_text += "\nCRITICAL: You MUST end your response with exactly [NEXT_STEP_REQUIRED] (to continue the agent loop) OR [TASK_COMPLETE] Your Message (to finish and return to chat)."

    dynamic_system_prompt = load_dynamic_skills(user_prompt, step)
    full_prompt = f"System:\n{dynamic_system_prompt}\n\n{prompt_text}"

    try:
        content = safe_generate_content(full_prompt, image_base64=image_base64, stream_callback=stream_callback)
        content = content.strip()
        
        # Parse thought block
        thought = ""
        if "<thought>" in content and "</thought>" in content:
            thought = content.split("<thought>")[1].split("</thought>")[0].strip()
            
        # Parse scratchpad
        new_scratchpad = ""
        if "<SCRATCHPAD>" in content and "</SCRATCHPAD>" in content:
            new_scratchpad = content.split("<SCRATCHPAD>")[1].split("</SCRATCHPAD>")[0].strip()
            
        # Parse code robustly
        code = ""
        code_type = "python"
        
        last_powershell_idx = content.rfind("[POWERSHELL]")
        last_code_idx = content.rfind("[CODE GENERATED]")
        last_md_py_idx = content.rfind("```python")
        last_md_ps_idx = content.rfind("```powershell")
        
        max_idx = max(last_powershell_idx, last_code_idx, last_md_py_idx, last_md_ps_idx)
        
        if max_idx != -1:
            if max_idx == last_powershell_idx:
                code_type = "powershell"
                code = content[last_powershell_idx + len("[POWERSHELL]"):].strip()
                code = code.split("[/POWERSHELL]")[0].strip()
            elif max_idx == last_code_idx:
                code_type = "python"
                code = content[last_code_idx + len("[CODE GENERATED]"):].strip()
                code = code.split("[/CODE GENERATED]")[0].strip()
            elif max_idx == last_md_py_idx:
                code_type = "python"
                code = content[last_md_py_idx + len("```python"):].strip()
                code = code.split("```")[0].strip()
            elif max_idx == last_md_ps_idx:
                code_type = "powershell"
                code = content[last_md_ps_idx + len("```powershell"):].strip()
                code = code.split("```")[0].strip()
                
            for tag in ["[NEXT_STEP_REQUIRED]", "[TASK_COMPLETE]", "\n[NEXT", "\n[TASK"]:
                if tag in code:
                    code = code.split(tag)[0].strip()
            
        last_task_complete_idx = content.rfind("[TASK_COMPLETE]")
        last_next_step_idx = content.rfind("[NEXT_STEP_REQUIRED]")
        
        status = "COMPLETE" 
        if last_task_complete_idx > last_next_step_idx:
            status = "COMPLETE"
        elif last_next_step_idx > last_task_complete_idx:
            status = "CONTINUE"
            
        final_message = "Task finished successfully."
        if status == "COMPLETE" and last_task_complete_idx != -1:
            raw_final = content[last_task_complete_idx + len("[TASK_COMPLETE]"):].strip()
            if raw_final:
                final_message = raw_final
                for tag in ["</thought>", "<SCRATCHPAD>", "</SCRATCHPAD>", "[CODE GENERATED]", "```python", "```powershell"]:
                    final_message = final_message.split(tag)[0].strip()
            
        return {
            "thought": thought,
            "scratchpad": new_scratchpad,
            "code": code,
            "status": status,
            "final_message": final_message,
            "code_type": code_type,
            "raw": content
        }
    except Exception as e:
        return {"error": f"Error communicating with LLM: {str(e)}"}
