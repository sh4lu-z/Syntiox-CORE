---
name: Python Sandbox
description: Executes arbitrary Python code securely and installs pip packages using MCP.
keywords: python, sandbox, code, script, pip, run, execute, install package
---

# Python Sandbox Skill (MCP)
You have the ability to run arbitrary Python code in a secure sandbox and install pip packages using the `mcp_runner` helper.
When the user asks you to execute a generic python script (that isn't part of normal agent operations) or install a package, use this skill.

**IMPORTANT:** 
1. Use `sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))` (since code runs in the workspace folder) to ensure `backend.mcp_runner` can be imported.
2. The MCP server path is `MCP/python_sandbox_mcp.py` (relative to the project root).

## Available Tools:
1. **`run_python`**: Runs a python code snippet.
   - Arguments: `code` (string), `timeout_seconds` (number), `working_dir` (string)
2. **`run_python_file`**: Runs an existing python file.
   - Arguments: `file_path` (string), `args` (list of strings), `timeout_seconds` (number)
3. **`install_package`**: Installs a python package via pip.
   - Arguments: `package_name` (string)

### Code Example for Running a Python Snippet:
```python
import sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

my_code = '''
def hello():
    print("Hello from sandbox!")
hello()
'''

result = run_mcp_tool(
    os.path.join(os.path.abspath(os.path.join(os.getcwd(), "..")), "MCP", "python_sandbox_mcp.py"),
    "run_python",
    {
        "code": my_code,
        "timeout_seconds": 15
    }
)
print(result)
```

### Code Example for Installing a Package:
```python
import sys
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..")))
from backend.mcp_runner import run_mcp_tool

result = run_mcp_tool(
    os.path.join(os.path.abspath(os.path.join(os.getcwd(), "..")), "MCP", "python_sandbox_mcp.py"),
    "install_package",
    {"package_name": "requests"}
)
print(result)
```
