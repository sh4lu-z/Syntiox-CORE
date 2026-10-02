import os
import sys
import json
from TOOLS.core.logger import action_logger

@action_logger("spawn_subagent")
def spawn_subagent(task: str, system_prompt: str) -> str:
    """
    Spawns a sub-agent with access to ALL tools to complete a specific task.
    You can provide a 100% custom system prompt to define the sub-agent's behavior.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    from backend.cloud_llm import safe_generate_content, route_skills_and_tools, SKILLS_CACHE, preload_skills
    from backend.tools_loader import get_json_tools
    from backend.executor import execute_tool
    from google.genai import types

    print(f"\n[Sub-Agent] Routing Skills and Tools for task: {task}...")
    routed_result = route_skills_and_tools(task, "")
    
    # 1. Load dynamically routed tools
    tools_schema = get_json_tools("TOOLS", active_skills=routed_result)
    gemini_funcs = []
    for t in tools_schema:
        fn = t.get("function", {})
        gemini_funcs.append(types.FunctionDeclaration(
            name=fn.get("name"),
            description=fn.get("description"),
            parameters=fn.get("parameters")
        ))
        
    # 2. Load dynamically routed skills
    preload_skills()
    skill_instructions = []
    for skill in SKILLS_CACHE:
        kw = skill.get("keywords", [])
        if "always" in kw or "default" in kw or skill.get("name", "").lower() in routed_result.get("skills", []):
            body_with_paths = skill["body"].replace("{ROOT_DIR}", root_dir.replace('\\', '\\\\'))
            skill_instructions.append(body_with_paths)
            
    if skill_instructions:
        system_prompt += "\n\n[Active Skills Instructions]:\n" + "\n\n".join(skill_instructions)

    print(f"\n[Sub-Agent] Starting Task: {task}")
    
    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=f"Task: {task}")])
    ]
    
    for step in range(20):
        try:
            res = safe_generate_content(
                prompt_or_contents=contents,
                sys_prompt=system_prompt,
                tools=[types.Tool(function_declarations=gemini_funcs)] if gemini_funcs else None,
                max_output_tokens=8192
            )
        except Exception as e:
            return f"Sub-agent crashed: {str(e)}"

        ai_text = res.get("content", "")
        native_calls = res.get("native_function_call_parts", [])
        
        model_parts = []
        if ai_text:
            model_parts.append(types.Part.from_text(text=ai_text))
            
        tool_calls_to_execute = []
        for p in native_calls:
            call = p.function_call
            args_dict = dict(call.args) if getattr(call, 'args', None) else {}
            try:
                new_part = types.Part(function_call=types.FunctionCall(name=call.name, args=args_dict))
                if hasattr(p, 'thought_signature') and p.thought_signature:
                    new_part.thought_signature = p.thought_signature
                model_parts.append(new_part)
            except Exception:
                model_parts.append(types.Part.from_text(text=f"Called tool: {call.name}"))
            tool_calls_to_execute.append({"name": call.name, "args": args_dict})
            
        if not model_parts:
            model_parts.append(types.Part.from_text(text="Executing tools."))
            
        contents.append(types.Content(role="model", parts=model_parts))
        
        # If no tools were called, the sub-agent has finished its task
        if not tool_calls_to_execute:
            print(f"[Sub-Agent] Finished: {ai_text}")
            return ai_text
            
        response_parts = []
        for tc in tool_calls_to_execute:
            t_name = tc["name"]
            t_args = tc["args"]
            print(f"  [Sub-Agent Tool] Executing: {t_name}")
            
            try:
                result = execute_tool(t_name, t_args)
            except Exception as e:
                result = f"Error executing tool {t_name}: {str(e)}"
                
            try:
                response_parts.append(types.Part(function_response=types.FunctionResponse(
                    name=t_name, response={"result": str(result)[:10000]}
                )))
            except Exception:
                response_parts.append(types.Part.from_text(text=f"[Tool {t_name} result]: {str(result)[:10000]}"))
                
        contents.append(types.Content(role="user", parts=response_parts))

    return "Sub-agent stopped after reaching the maximum limit of 20 steps."
