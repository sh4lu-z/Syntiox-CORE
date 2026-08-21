import os
import sys
import importlib
import traceback

def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    Dynamically routes a JSON tool call to the corresponding python function inside the TOOLS directory.
    """
    tools_dir = os.path.abspath("TOOLS")
    if not os.path.exists(tools_dir):
        return f"Error: TOOLS directory not found at {tools_dir}"
        
    # Ensure root is in sys.path for absolute imports like TOOLS.file_utils
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    # Scan TOOLS directory for the module containing the tool_name
    target_module = None
    target_func = None
    
    for root, _, files in os.walk(tools_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file[:-3]
                rel_path = os.path.relpath(root, tools_dir)
                if rel_path == ".":
                    full_module_path = f"TOOLS.{module_name}"
                else:
                    pkg_path = rel_path.replace(os.sep, ".")
                    full_module_path = f"TOOLS.{pkg_path}.{module_name}"
                
                try:
                    # Dynamically import the module
                    mod = importlib.import_module(full_module_path)
                    
                    # Check if the tool_name exists as a callable attribute
                    if hasattr(mod, tool_name) and callable(getattr(mod, tool_name)):
                        target_func = getattr(mod, tool_name)
                        if getattr(target_func, "__module__", "") == mod.__name__:
                            target_module = full_module_path
                            break
                except Exception as e:
                    print(f"[Executor Error] Failed to import {full_module_path}: {e}")
                    
        if target_func:
            break
            
    if not target_func:
        return f"Error: Tool '{tool_name}' was not found in any module inside the TOOLS directory."
        
    # Attempt execution
    try:
        print(f"[Executor] Routing to {target_module}.{tool_name} with args: {arguments}")
        
        # Determine if we need to change directory to workspace for execution
        from backend.config_paths import WORKSPACE_DIR
        workspace_dir = WORKSPACE_DIR
        
        # Check if the function accepts 'cwd' or **kwargs
        import inspect
        sig = inspect.signature(target_func)
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if ('cwd' in sig.parameters or has_kwargs) and 'cwd' not in arguments:
            arguments['cwd'] = workspace_dir
            
        # Basic type coercion based on signature
        for param_name, param in sig.parameters.items():
            if param_name in arguments:
                val = arguments[param_name]
                if param.annotation == int:
                    try: arguments[param_name] = int(val)
                    except: pass
                elif param.annotation == bool:
                    try: 
                        if isinstance(val, str): arguments[param_name] = val.lower() in ('true', '1', 'yes', 'y')
                        else: arguments[param_name] = bool(val)
                    except: pass
                elif param.annotation == float:
                    try: arguments[param_name] = float(val)
                    except: pass
                    
        result = target_func(**arguments)
        
        # Convert result to string for LLM parsing
        return str(result)
        
    except Exception as e:
        error_msg = f"Error executing tool '{tool_name}': {str(e)}\n{traceback.format_exc()}"
        print(f"[Executor Error] {error_msg}")
        return error_msg

def analyze_tool_call(tool_name: str, arguments: dict) -> bool:
    """
    Determines if a tool call requires explicit user approval.
    """
    dangerous_tools = ["run_terminal_command", "delete_file"]
    
    if tool_name in dangerous_tools:
        # Check arguments for specific dangerous keywords if needed
        cmd = str(arguments.get("command", "")).lower()
        if "rm " in cmd or "del " in cmd or "format " in cmd:
            return True
            
    return False
