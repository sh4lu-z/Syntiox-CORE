import os
import ast
import json

def get_json_tools(tools_dir: str = "tools", active_skills=None) -> list:
    """Scans the tools directory and builds OpenAI-compatible JSON schemas for all core tools."""
    if not os.path.isabs(tools_dir):
        full_tools_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", tools_dir))
    else:
        full_tools_dir = tools_dir
    if not os.path.exists(full_tools_dir):
        return []
        
    tools_list = []
    
    for root, _, files in os.walk(full_tools_dir):
        for file in sorted(files):
            if file.endswith(".py") and not file.startswith("__") and file != "logger.py":
                filepath = os.path.join(root, file)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except Exception:
                    continue
                    
                for node in tree.body:
                    if isinstance(node, ast.FunctionDef):
                        if node.name.startswith("_"):
                            continue
                            
                        properties = {}
                        required_args = []
                        
                        def map_type(annotation):
                            if annotation and hasattr(ast, "Name") and isinstance(annotation, ast.Name):
                                if annotation.id == "int": return "integer"
                                elif annotation.id == "float": return "number"
                                elif annotation.id == "bool": return "boolean"
                                elif annotation.id == "dict": return "object"
                                elif annotation.id == "list": return "array"
                            return "string"
                            
                        all_args = []
                        if getattr(node.args, "args", None):
                            num_defaults = len(node.args.defaults)
                            num_args = len(node.args.args)
                            for i, arg in enumerate(node.args.args):
                                is_req = i < (num_args - num_defaults)
                                all_args.append((arg, is_req))
                                
                        if getattr(node.args, "kwonlyargs", None):
                            for i, arg in enumerate(node.args.kwonlyargs):
                                is_req = node.args.kw_defaults[i] is None
                                all_args.append((arg, is_req))

                        for arg, is_req in all_args:
                            arg_name = arg.arg
                            if arg_name == "self":
                                continue
                            arg_type = map_type(arg.annotation)
                            properties[arg_name] = {"type": arg_type, "description": f"The {arg_name} parameter."}
                            if node.name == "call_mcp_tool" and arg_name == "arguments":
                                properties[arg_name] = {
                                    "type": "object",
                                    "description": "JSON object of arguments matching the tool's inputSchema in mcp_schemas/<server_name>/<tool_name>.json"
                                }
                            elif arg_type == "array":
                                properties[arg_name]["items"] = {"type": "string"}
                            if is_req:
                                required_args.append(arg_name)

                        if node.name != "ask_user" and "requires_approval" not in properties:
                            properties["requires_approval"] = {
                                "type": "boolean",
                                "description": "Set to true ONLY if this action is destructive or modifies files outside the workspace."
                            }
                                
                        docstring = ast.get_docstring(node)
                        if not docstring:
                            docstring = f"Executes the {node.name} utility function."
                        else:
                            docstring = docstring.strip()
                            
                        tool_schema = {
                            "type": "function",
                            "function": {
                                "name": node.name,
                                "description": docstring,
                                "parameters": {
                                    "type": "object",
                                    "properties": properties,
                                    "required": required_args
                                }
                            }
                        }
                        tools_list.append(tool_schema)
                        
    return tools_list

def generate_tools_prompt(tools_dir: str = "tools") -> str:
    return ""

if __name__ == "__main__":
    tools = get_json_tools("tools")
    print(json.dumps(tools, indent=2))
