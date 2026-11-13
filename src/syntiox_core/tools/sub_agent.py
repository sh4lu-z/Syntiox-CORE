import os
import sys
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
    from backend.cloud_llm import (
        safe_generate_content,
        load_dynamic_skills,
        parse_text_tool_calls,
        _init_loop_memory,
        compact_and_build_history_contents,
        GOOGLE_MODEL,
        THINKING_LEVEL,
    )
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

    initial_contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=f"Task: {task}")])
    ]
    loop_history = []
    loop_memory = _init_loop_memory()
    recovery_attempts = 0

    def subagent_thought_callback(chunk):
        state.emit_event({
            "event": "thinking",
            "agent_id": "subagent",
            "data": chunk,
        })

    for step in range(20):
        if getattr(state, "STOP_REQUESTED", False):
            return "Sub-agent stopped by user."

        contents = list(initial_contents) + compact_and_build_history_contents(
            loop_history,
            loop_memory=loop_memory,
            target_model=GOOGLE_MODEL,
        )
        if contents and contents[-1].role == "model":
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text="Please proceed with the next step or provide your final response.")]
            ))

        try:
            res = safe_generate_content(
                prompt_or_contents=contents,
                sys_prompt=system_prompt,
                tools=[types.Tool(function_declarations=gemini_funcs)] if gemini_funcs else None,
                max_output_tokens=8192,
                thought_callback=subagent_thought_callback,
                thinking_level=THINKING_LEVEL,
                include_thoughts=True,
            )
        except Exception as e:
            return f"Sub-agent crashed: {str(e)}"

        ai_text = res.get("content", "")
        ai_thinking = res.get("thoughts", "")
        native_calls = res.get("native_function_call_parts", [])
        
        tool_calls_to_execute = []
        if native_calls:
            for p in native_calls:
                call = p.function_call
                args_dict = dict(call.args) if getattr(call, 'args', None) else {}
                tool_calls_to_execute.append({
                    "type": "function",
                    "function": {"name": call.name, "arguments": args_dict},
                    "call_id": getattr(call, "id", None),
                    "thought_signature": getattr(p, "thought_signature", None),
                })
        elif ai_text and "<call:" in ai_text:
            tool_calls_to_execute = parse_text_tool_calls(ai_text)

        if not tool_calls_to_execute:
            if ("[SYSTEM_RECOVERY_REQUIRED]" in ai_text or (ai_thinking.strip() and not ai_text.strip())) and recovery_attempts < 2:
                recovery_attempts += 1
                loop_history.append({
                    "step": step + 1,
                    "thought": ai_text,
                    "thinking": ai_thinking,
                    "tool_calls": [{
                        "function": {"name": "system_recovery", "arguments": {}},
                        "result": "CRITICAL ERROR: Your response or tool call was malformed or missing. Invoke your next tool cleanly or provide your final text response.",
                    }],
                    "execution_result": "Malformed response recovery.",
                })
                continue
            print(f"[Sub-Agent] Finished: {ai_text}")
            return ai_text

        recovery_attempts = 0
        if getattr(state, "STOP_REQUESTED", False):
            return "Sub-agent stopped by user."

        for tc in tool_calls_to_execute:
            t_name = tc["function"]["name"]
            t_args = tc["function"]["arguments"]
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
            tc["result"] = result

        loop_history.append({
            "step": step + 1,
            "thought": ai_text,
            "thinking": ai_thinking,
            "tool_calls": tool_calls_to_execute,
            "execution_result": "\n\n".join(str(tc.get("result", "")) for tc in tool_calls_to_execute),
        })

    return "Sub-agent stopped after reaching the maximum limit of 20 steps."
