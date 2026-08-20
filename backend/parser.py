import json
import re

def extract_tool_calls(text: str) -> list:
    """
    Extracts tool calls formatted as XML tags:
    <tool_call>{"name": "func", "arguments": {"arg": "val"}}</tool_call>
    Ignores tags that are wrapped inside markdown code blocks to prevent accidental execution during explanations.
    """
    tool_calls = []
    
    # 1. Strip out markdown code blocks to prevent accidental parsing
    safe_text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    safe_text = re.sub(r'`.*?`', '', safe_text, flags=re.DOTALL)
    
    # 2. Find all <tool_call> blocks
    pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
    matches = re.finditer(pattern, safe_text, flags=re.DOTALL)
    
    for match in matches:
        json_str = match.group(1)
        
        try:
            # Fix unquoted JSON keys, but ONLY if they follow { or , to avoid breaking C: paths inside strings
            fixed_json_str = re.sub(r'([\{,]\s*)(?<!["\'])\b([a-zA-Z_][a-zA-Z0-9_]*)\b(\s*:)', r'\1"\2"\3', json_str)
            
            # Try to parse
            try:
                parsed_data = json.loads(fixed_json_str)
            except json.JSONDecodeError:
                # If it fails, maybe it has single quotes. Try replacing them carefully.
                alt_json = fixed_json_str.replace("'", '"')
                parsed_data = json.loads(alt_json)
            
            if "name" in parsed_data:
                args = parsed_data.get("arguments")
                if args is None:
                    args = {k: v for k, v in parsed_data.items() if k != "name"}
                    
                tool_calls.append({
                    "type": "function",
                    "function": {
                        "name": parsed_data["name"],
                        "arguments": args
                    }
                })
            else:
                print(f"\033[93m[Parser Warning] XML JSON missing 'name': {parsed_data}\033[0m")
                
        except json.JSONDecodeError as e:
            print(f"\033[93m[Parser Warning] XML JSON parse error: {e}\033[0m")
            
    return tool_calls
