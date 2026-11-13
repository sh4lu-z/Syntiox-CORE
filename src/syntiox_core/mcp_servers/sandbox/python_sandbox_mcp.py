#!/usr/bin/env python3
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
"""
Python Code Sandbox MCP Server - Windows Compatible Fix
"""

import asyncio
import subprocess
import tempfile
import os
import textwrap
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("python-sandbox")

TIMEOUT_DEFAULT = 15
TIMEOUT_MAX     = 60

_executor = ThreadPoolExecutor(max_workers=4)


def _run_code_sync(python_exe: str, script_path: str, cwd: str, timeout: float) -> tuple[str, str, int]:
    """Synchronous subprocess run - Windows compatible."""
    try:
        result = subprocess.run(
            [python_exe, script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", f"TIMEOUT:{timeout}", -1
    except Exception as e:
        return "", f"ERROR:{e}", -1


def _run_file_sync(python_exe: str, file_path: str, cli_args: list, cwd: str, timeout: float) -> tuple[str, str, int]:
    try:
        result = subprocess.run(
            [python_exe, file_path] + cli_args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", f"TIMEOUT:{timeout}", -1
    except Exception as e:
        return "", f"ERROR:{e}", -1


def _install_sync(python_exe: str, package: str) -> tuple[str, str, int]:
    try:
        result = subprocess.run(
            [python_exe, "-m", "pip", "install", package],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT:120", -1
    except Exception as e:
        return "", f"ERROR:{e}", -1


def get_python_exe() -> str:
    """Get correct Python executable path."""
    return sys.executable


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="python_sandbox",
            description=textwrap.dedent("""\
                Execute Python code snippets, run script files, or install pip packages.
                - To run code: provide `code` (e.g. "print('hello')").
                - To run a file: provide `file_path` and optional `args`.
                - To install package: provide `package_name` (e.g. "requests").
                - Optional params: `action` ('run_code', 'run_file', 'install'), `timeout_seconds`, `working_dir`.
            """),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code snippet to execute"},
                    "file_path": {"type": "string", "description": "Path to Python (.py) file to execute"},
                    "package_name": {"type": "string", "description": "Package name to install via pip"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "CLI arguments for file execution"},
                    "action": {"type": "string", "description": "Action: 'run_code', 'run_file', 'install' (auto-detected if omitted)"},
                    "timeout_seconds": {"type": "number", "description": "Timeout seconds (default 15, max 60)"},
                    "working_dir": {"type": "string", "description": "Working directory path (optional)"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    loop = asyncio.get_running_loop()

    action = (arguments.get("action") or "").strip().lower()
    code: str = arguments.get("code", "").strip()
    file_path = arguments.get("file_path", "")
    package = arguments.get("package_name", "").strip()
    timeout = min(float(arguments.get("timeout_seconds", TIMEOUT_DEFAULT)), TIMEOUT_MAX)
    working_dir = arguments.get("working_dir") or os.getcwd()
    cli_args = [str(a) for a in arguments.get("args", [])]

    # Package install
    if name == "install_package" or action in ("install", "install_package") or (package and not code and not file_path):
        if not package or any(c in package for c in [";", "&", "|", "`"]) or package.startswith("-"):
            return [TextContent(type="text", text="Invalid package name.")]

        stdout, stderr, rc = await loop.run_in_executor(
            _executor, _install_sync, get_python_exe(), package
        )
        return [TextContent(type="text", text=_format_result(stdout, stderr, rc, 120))]

    # File execution
    elif name == "run_python_file" or action in ("run_file", "file") or (file_path and not code):
        p = Path(file_path)
        if not p.exists():
            return [TextContent(type="text", text=f"File not found: {file_path}")]

        target_cwd = working_dir if arguments.get("working_dir") else str(p.parent)
        stdout, stderr, rc = await loop.run_in_executor(
            _executor,
            _run_file_sync,
            get_python_exe(), str(p), cli_args, target_cwd, timeout
        )
        return [TextContent(type="text", text=_format_result(stdout, stderr, rc, timeout))]

    # Code execution (default)
    elif name in ("run_python", "python_sandbox") or action in ("run", "run_code") or code:
        if not code:
            return [TextContent(type="text", text="Error: Code, file_path, or package_name is required.")]

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        )
        tmp.write(code)
        tmp.close()

        try:
            stdout, stderr, rc = await loop.run_in_executor(
                _executor,
                _run_code_sync,
                get_python_exe(), tmp.name, working_dir, timeout
            )
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        return [TextContent(type="text", text=_format_result(stdout, stderr, rc, timeout))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


def _format_result(stdout: str, stderr: str, rc: int, timeout: float) -> str:
    if stderr.startswith("TIMEOUT:"):
        return f"Timeout: Code execution exceeded {timeout}s limit."
    if stderr.startswith("ERROR:"):
        return f"Error: {stderr[6:]}"

    parts = []
    if stdout:
        parts.append(f"stdout:\n{stdout}")
    if stderr:
        parts.append(f"stderr:\n{stderr}")
    if rc == 0:
        parts.append("Exit code: 0" if (stdout or stderr) else "Executed successfully (no output).")
    else:
        parts.append(f"Exit code: {rc}")
    return "\n\n".join(parts)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
