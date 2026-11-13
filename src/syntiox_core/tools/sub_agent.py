import os
import sys
import json
from tools.logger import action_logger

@action_logger("spawn_subagent")
def spawn_subagent(task: str, system_prompt: str) -> str:
    """
    Spawns a sub-agent with access to ALL tools to complete a specific task.
    You can provide a 100% custom system prompt to define the sub-agent's behavior.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    from backend import state
    from backend.cloud_llm import safe_generate_content, load_dynamic_skills
    from backend.tools_loader import get_json_tools
    from backend.executor import execute_tool, analyze_tool_call
    from google.genai import types

    # 1. Load all core tools (excluding spawn_subagent to prevent recursion)
    tools_schema = get_json_tools("tools")
    gemini_funcs = []
    for t in tools_schema:
        fn = t.get("function", {})
        if fn.get("name") == "spawn_subagent":
            continue
        gemini_funcs.append(types.FunctionDeclaration(
            name=fn.get("name"),
            description=fn.get("description"),
            parameters=fn.get("parameters")
        ))
        
    # 2. Load default skills, on-demand skill index, and lazy MCP schemas index
    skills_block = load_dynamic_skills()
    if skills_block:
        system_prompt += "\n\n[Active Skills & MCP Instructions]:\n" + skills_block

    ws_info = state.get_workspace_info()
    ws_label = ws_info["workspace"] if ws_info["workspace"] else "None (using Scratch directory)"
    system_prompt += (
        f"\n\n[WORKSPACE DIRECTORY]: {ws_label}\n"
        f"[SCRATCH DIRECTORY]: {ws_info['scratch_dir']}\n"
        f"Use the Workspace Directory for user project files and commands when set; use the Scratch Directory for temporary files or when no workspace is set.\n"
    )

    print(f"\n[Sub-Agent] Starting Task: {task}")
    
    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=f"Task: {task}")])
    ]
    
    for step in range(20):
        if getattr(state, "STOP_REQUESTED", False):
            return "Sub-agent stopped by user."

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
            part_ok = False
            try:
                new_part = types.Part(function_call=types.FunctionCall(name=call.name, args=args_dict))
                if hasattr(p, 'thought_signature') and p.thought_signature:
                    new_part.thought_signature = p.thought_signature
                model_parts.append(new_part)
                part_ok = True
            except Exception:
                model_parts.append(types.Part.from_text(text=f"Called tool: {call.name}"))
            tool_calls_to_execute.append({"name": call.name, "args": args_dict, "native_part": part_ok})
            
        if not model_parts:
            model_parts.append(types.Part.from_text(text="Executing tools."))
            
        contents.append(types.Content(role="model", parts=model_parts))
        
        if not tool_calls_to_execute:
            print(f"[Sub-Agent] Finished: {ai_text}")
            return ai_text
            
        if getattr(state, "STOP_REQUESTED", False):
            return "Sub-agent stopped by user."

        response_parts = []
        for tc in tool_calls_to_execute:
            t_name = tc["name"]
            t_args = tc["args"]
            print(f"  [Sub-Agent Tool] Executing: {t_name}")
            state.emit_event({
                "event": "state",
                "agent_id": "subagent",
                "status": f"Running {t_name}"
            })
            state.emit_event({
                "event": "tool_call",
                "agent_id": "subagent",
                "tool": t_name,
                "args": t_args
            })
            
            if analyze_tool_call(t_name, t_args):
                from backend import interaction_manager
                state.emit_event({
                    "event": "state",
                    "agent_id": "subagent",
                    "status": f"Awaiting approval for {t_name}"
                })
                approved = interaction_manager.request_approval(
                    agent_id="subagent",
                    tool_name=t_name,
                    tool_args=t_args,
                )
                if approved:
                    try:
                        result = execute_tool(t_name, t_args)
                    except Exception as e:
                        result = f"Error executing tool {t_name}: {str(e)}"
                else:
                    result = f"Action blocked: User denied permission to execute '{t_name}'."
            else:
                try:
                    result = execute_tool(t_name, t_args)
                except Exception as e:
                    result = f"Error executing tool {t_name}: {str(e)}"
                
            state.emit_event({
                "event": "tool_result",
                "agent_id": "subagent",
                "tool": t_name,
                "output": str(result)[:2000]
            })
                
            if tc.get("native_part"):
                try:
                    response_parts.append(types.Part(function_response=types.FunctionResponse(
                        name=t_name, response={"result": str(result)[:10000]}
                    )))
                except Exception:
                    response_parts.append(types.Part.from_text(text=f"[Tool {t_name} result]: {str(result)[:10000]}"))
            else:
                response_parts.append(types.Part.from_text(text=f"[Tool {t_name} result]: {str(result)[:10000]}"))
                
        contents.append(types.Content(role="user", parts=response_parts))

    return "Sub-agent stopped after reaching the maximum limit of 20 steps."
