try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

import os
import glob
from dotenv import load_dotenv
from backend import state
from backend.config_paths import ENV_FILE, WORKSPACE_DIR

# .env ෆයිල් එක ලෝඩ් කරමු
load_dotenv(ENV_FILE)

base_model_path = os.getenv("MODEL_PATH", r"F:\12_AI_MODELS\google\gemma-4-E4B-it-GGUF\gemma-4-E4B-it-Q4_K_M.gguf")
n_ctx_val = int(os.getenv("MODEL_CTX", "16000"))
n_gpu_layers_val = int(os.getenv("MODEL_GPU_LAYERS", "30"))
n_batch_val = int(os.getenv("MODEL_BATCH_SIZE", "512"))

if Llama is not None:
    print("Loading Native LLM (Gemma)... Please wait.")
    llm = Llama(
        model_path=base_model_path,
        n_ctx=n_ctx_val, 
        n_threads=0, 
        n_threads_batch=0,
        n_batch=n_batch_val,
        n_gpu_layers=n_gpu_layers_val,
        use_mlock=False,
        use_mmap=True,
        echo=False,
        verbose=False
    )
    print("LLM Loaded Successfully!")
else:
    print("llama_cpp is not installed. Local LLM will not be available.")
    llm = None

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
        
    prompt = f"<start_of_turn>user\nYou are a Skill Router for an AI Agent. Your job is to select the most appropriate skills needed to fulfill the user's request.\n\nAvailable Skills:\n{skill_descriptions}\n\nRecent Chat History:\n{history_str}\n\nUser Request: {user_prompt}\n\nReply ONLY with a comma-separated list of the exact Skill names required. If no skills are needed, reply with NONE.<end_of_turn>\n<start_of_turn>model\n"
    
    try:
        response = llm.create_completion(prompt=prompt, max_tokens=100, temperature=0.1, stop=["<end_of_turn>"])
        content = response["choices"][0]["text"].strip()
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
    """
    If history is too long (e.g. > 6 turns), summarize the older portion and keep the latest few turns.
    Returns the new compacted chat history list.
    """
    if len(chat_history_list) <= 6:
        return chat_history_list
        
    recent_turns = chat_history_list[-3:]
    old_turns = chat_history_list[:-3]
    
    old_history_str = "\n".join(old_turns)
    
    prompt = f"<start_of_turn>user\nYou are an AI assistant. Please write a highly concise summary of the following past conversation so we don't forget the context. Keep important facts, paths, and goals. Output only the summary.\n\nConversation to summarize:\n{old_history_str}<end_of_turn>\n<start_of_turn>model\n"
    
    try:
        response = llm.create_completion(
            prompt=prompt,
            max_tokens=250,
            temperature=0.3,
            stop=["<end_of_turn>"]
        )
        summary = response["choices"][0]["text"].strip()
        new_history = [f"[System: Summary of older conversation] {summary}"] + recent_turns
        return new_history
    except:
        # If summarization fails, just truncate to save context limit
        return chat_history_list[-6:]


def classify_intent(user_prompt: str, manual_override: str = None, history_str: str = "") -> str:
    """
    Returns 'CHAT' if it's just a normal conversation.
    Returns 'AGENT' if it requires executing tasks, scripts, or OS manipulation.
    If manual_override is provided, forces the mode.
    """
    if manual_override:
        return manual_override.upper()
        
    prompt = f"<start_of_turn>user\nYou are an intent classifier. Respond with EXACTLY 'CHAT' or 'AGENT'.\n- If the user wants you to do something on their computer, write code, run commands, inspect local files/paths, execute a plan, search the web, do a math calculation, run python code, or use a tool. ALSO, if the user asks ANY factual question, asks about a person, event, movie, or anything that requires internet/up-to-date knowledge (e.g., 'who is X?', 'what is Y?', 'best movies of 2026', 'search for x'), you MUST say 'AGENT' so it can use the web search tool.\n- If they are ONLY greeting you (e.g., 'hello', 'how are you') or making casual conversational remarks that require absolutely no research or tools, say 'CHAT'.\n\nRecent Chat History:\n{history_str}\n\nUser Input: {user_prompt}<end_of_turn>\n<start_of_turn>model\n"
    
    try:
        response = llm.create_completion(
            prompt=prompt,
            max_tokens=10,
            temperature=0.1,
            stop=["<end_of_turn>"]
        )
        content = response["choices"][0]["text"].strip().upper()
        if "AGENT" in content:
            return "AGENT"
        return "CHAT"
    except Exception as e:
        return "AGENT" # Default to agent if fails

def generate_session_title(user_prompt: str) -> str:
    """Generates a short title for the session based on the first prompt."""
    prompt = f"<start_of_turn>user\nYou are a title generator. Generate a very short (2-5 words) title for this conversation based on the user's first prompt. Do not use quotes or prefixes, just the title.\n\nUser Input: {user_prompt}<end_of_turn>\n<start_of_turn>model\n"
    try:
        response = llm.create_completion(
            prompt=prompt,
            max_tokens=15,
            temperature=0.3,
            stop=["<end_of_turn>"]
        )
        return response["choices"][0]["text"].strip()
    except:
        return "Untitled Session"

def generate_chat_response(user_prompt: str, history_str: str = "", stream_callback=None) -> str:
    """Handles normal conversational chat."""
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
    prompt = f"<start_of_turn>user\n{dynamic_system_prompt}{walkthrough_context}\n\nRecent Conversation History:\n{history_str}\n\nUser: {user_prompt}<end_of_turn>\n<start_of_turn>model\n"
    try:
        response = llm.create_completion(
            prompt=prompt,
            max_tokens=512,
            temperature=0.7,
            stop=["<end_of_turn>"],
            stream=True
        )
        content = ""
        for chunk in response:
            token = chunk["choices"][0]["text"]
            content += token
            if stream_callback:
                stream_callback(token)
        
        import re
        content = re.sub(r'<\|?channel\|?>thought.*?<channel\|?>', '', content, flags=re.DOTALL)
        content = re.sub(r'<thought>.*?</thought>', '', content, flags=re.DOTALL)
        
        return content.strip()
    except Exception as e:
        return f"Error: {e}"


def generate_agent_step(user_prompt: str, loop_history: list, step: int = 1, history_str: str = "", task_list_str: str = "", stream_callback=None, **kwargs) -> dict:
    from backend.tools_loader import get_json_tools
    from backend.parser import extract_tool_calls
    import json
    
    messages = []
    
    dynamic_system_prompt = load_dynamic_skills(user_prompt, step, history_str)
    sys_prompt = f"{dynamic_system_prompt}\n"
    
    if history_str:
        sys_prompt += f"Recent Chat History:\n{history_str}\n"
        
    if task_list_str:
        sys_prompt += f"Current Task Plan (task.md):\n{task_list_str}\n"
        
    tools_schema = get_json_tools("TOOLS")
    sys_prompt += "\n\nYou have access to the following TOOLS. If you need to perform an action, you MUST output a Tool Call using this EXACT XML format:\n"
    sys_prompt += "<tool_call>{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"value\"}}</tool_call>\n"
    sys_prompt += "Example: <tool_call>{\"name\": \"run_terminal_command\", \"arguments\": {\"command\": \"dir\"}}</tool_call>\n"
    sys_prompt += "CRITICAL RULE: If you are explaining tool usage to the user, DO NOT use the raw <tool_call> tags. You MUST wrap them in markdown backticks (```). Only use raw unescaped tags when you ACTUALLY want to execute the tool.\n"
    sys_prompt += "CRITICAL: NEVER use LaTeX (like \\mathrm), markdown, or any text formatting inside the JSON braces. It must be valid, raw JSON.\n"
    sys_prompt += "CRITICAL: When writing Windows file paths inside JSON, you MUST double-escape backslashes (e.g. C:\\\\Users\\\\Desktop). DO NOT use single backslashes.\n"
    sys_prompt += "You can output multiple tools consecutively to run them concurrently.\n\nAVAILABLE TOOLS:\n"
    sys_prompt += json.dumps(tools_schema, indent=2) + "\n\n"
    sys_prompt += "If you are just talking to the user and don't need tools, output standard text."
    
    messages.append({"role": "system", "content": sys_prompt})
    
    for item in loop_history:
        if item.get("tool_calls"):
            messages.append({
                "role": "assistant", 
                "content": item.get("thought", "Executed tool.")
            })
            tool_names = ", ".join([tc["function"]["name"] for tc in item["tool_calls"]])
            messages.append({
                "role": "user",
                "content": f"[System] Tools [{tool_names}] executed. Results:\n{item.get('execution_result')}"
            })
        else:
            messages.append({
                "role": "assistant",
                "content": item.get("final_message", "")
            })
            
    if len(messages) > 1 and messages[-1]["role"] == "assistant":
        messages.append({
            "role": "user",
            "content": "Please proceed with the next step or provide your final response."
        })
        
    messages.append({"role": "user", "content": f"User Request: {user_prompt}"})
    
    try:
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=8192,
            temperature=0.2,
            stream=True
        )
        
        full_response = ""
        for chunk in response:
            if getattr(state, 'STOP_REQUESTED', False):
                full_response += "\n\n[System: Generation stopped by user]\n[TASK_COMPLETE]"
                break
            
            delta = chunk["choices"][0].get("delta", {})
            if "content" in delta and delta["content"]:
                token = delta["content"]
                full_response += token
                if stream_callback:
                    stream_callback(token)
                    
        # --- PARSE TOOL CALLS MANUALLY ---
        tool_calls = extract_tool_calls(full_response)
        
        status = "CONTINUE" if tool_calls else "COMPLETE"
        
        return {
            "thought": full_response,
            "tool_calls": tool_calls,
            "status": status,
            "final_message": full_response if status == "COMPLETE" else "",
            "raw": full_response
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Error communicating with Local LLM: {str(e)}"}
