import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_py_sandbox_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "python_sandbox_mcp.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("run_python")
def run_python(code: str, timeout_seconds: int = 15, working_dir: str = "") -> str:
    """
    Executes a Python code snippet.
    - code: Python code string
    - timeout_seconds: default 15s, max 60s
    - working_dir: working directory path
    """
    return _run_py_sandbox_mcp("run_python", {
        "code": code,
        "timeout_seconds": timeout_seconds,
        "working_dir": working_dir
    })

@action_logger("run_python_file")
def run_python_file(file_path: str, args: list = [], timeout_seconds: int = 15) -> str:
    """
    Executes an existing Python (.py) file.
    - file_path: .py file path
    - args: command line arguments (optional)
    - timeout_seconds: default 15s, max 60s
    """
    return _run_py_sandbox_mcp("run_python_file", {
        "file_path": file_path,
        "args": args,
        "timeout_seconds": timeout_seconds
    })

@action_logger("install_package")
def install_package(package_name: str) -> str:
    """
    Installs a Python package using pip.
    - package_name: Package name (e.g. 'requests', 'numpy==1.26.0')
    """
    return _run_py_sandbox_mcp("install_package", {
        "package_name": package_name
    })
