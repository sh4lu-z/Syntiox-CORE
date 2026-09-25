import os
import ast
import json

def get_json_tools(tools_dir: str = "TOOLS", active_skills: list = None) -> list:
    """Scans the TOOLS directory and builds OpenAI-compatible JSON schemas for all tools."""
    full_tools_dir = os.path.abspath(tools_dir)
    if not os.path.exists(full_tools_dir):
        return []
        
    if active_skills is None:
        active_skills = []
        
    tools_list = []
    
    for root, _, files in os.walk(full_tools_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                filepath = os.path.join(root, file)
                
                # Check for dynamic tools filtering
                rel_path = os.path.relpath(filepath, full_tools_dir)
                path_parts = rel_path.split(os.sep)
                
                if path_parts[0] == "dynamic":
                    # Tool is in TOOLS/dynamic/
                    # Match by folder name (e.g. dynamic/web_dev/tool.py) or file name (e.g. dynamic/web_dev.py)
                    skill_name_folder = path_parts[1] if len(path_parts) > 2 else ""
                    skill_name_file = file[:-3]
                    
                    if skill_name_folder not in active_skills and skill_name_file not in active_skills:
                        continue  # Skip loading this dynamic tool
                        
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except Exception:
                    continue
                    
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Skip private functions
                        if node.name.startswith("_"):
                            continue
                            
                        # Extract arguments
                        properties = {}
                        required_args = []
                        
                        # Handle regular arguments
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
                            if arg_name == "self": continue
                            arg_type = map_type(arg.annotation)
                            properties[arg_name] = {"type": arg_type, "description": f"The {arg_name} parameter."}
                            if is_req: required_args.append(arg_name)
                                
                        # Get docstring
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

def generate_tools_prompt(tools_dir: str = "TOOLS") -> str:
    """Legacy function for fallback, or we can just return an empty string if LLM uses native tools."""
    return ""

if __name__ == "__main__":
    tools = get_json_tools("TOOLS")
    print(json.dumps(tools, indent=2))
