import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_nodejs_sandbox_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "nodejs_sandbox_mcp.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("run_nodejs")
def run_nodejs(code: str, timeout_seconds: int = 15, working_dir: str = "") -> str:
    """
    Executes a NodeJS code snippet.
    - code: NodeJS code string
    - timeout_seconds: default 15s, max 60s
    - working_dir: working directory path
    """
    return _run_nodejs_sandbox_mcp("run_nodejs", {
        "code": code,
        "timeout_seconds": timeout_seconds,
        "working_dir": working_dir
    })

@action_logger("run_nodejs_file")
def run_nodejs_file(file_path: str, args: list = [], timeout_seconds: int = 15) -> str:
    """
    Executes an existing NodeJS (.js) file.
    - file_path: .js file path
    - args: command line arguments (optional)
    - timeout_seconds: default 15s, max 60s
    """
    return _run_nodejs_sandbox_mcp("run_nodejs_file", {
        "file_path": file_path,
        "args": args,
        "timeout_seconds": timeout_seconds
    })

@action_logger("install_npm_package")
def install_npm_package(package_name: str, working_dir: str) -> str:
    """
    Installs a NodeJS package using npm.
    - package_name: Package name (e.g. 'axios', 'express')
    - working_dir: Absolute path to the directory to install the package in (where node_modules will reside).
    """
    return _run_nodejs_sandbox_mcp("install_npm_package", {
        "package_name": package_name,
        "working_dir": working_dir
    })
