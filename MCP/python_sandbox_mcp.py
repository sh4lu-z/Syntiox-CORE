#!/usr/bin/env python3
"""
Python Code Sandbox MCP Server - Windows Compatible Fix
"""

import asyncio
import subprocess
import sys
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
            name="run_python",
            description=textwrap.dedent("""\
                Python code snippet execute කරනවා.
                - `code`: Python code string
                - `timeout_seconds`: default 15s, max 60s (optional)
                - `working_dir`: working directory path (optional)
                - print() use කරලා output show කරන්න
            """),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Execute කරන Python code"},
                    "timeout_seconds": {"type": "number", "description": "Timeout seconds (default 15, max 60)"},
                    "working_dir": {"type": "string", "description": "Working directory (optional)"},
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="run_python_file",
            description=textwrap.dedent("""\
                Existing Python (.py) file execute කරනවා.
                - `file_path`: .py file path
                - `args`: command line arguments (optional)
                - `timeout_seconds`: default 15s, max 60s (optional)
            """),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Python file path"},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "CLI arguments"},
                    "timeout_seconds": {"type": "number"},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="install_package",
            description="pip install command එකෙන් Python package install කරනවා.",
            inputSchema={
                "type": "object",
                "properties": {
                    "package_name": {"type": "string", "description": "Package name (e.g. 'requests', 'numpy==1.26.0')"},
                },
                "required": ["package_name"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    loop = asyncio.get_event_loop()

    if name == "run_python":
        code: str = arguments.get("code", "").strip()
        timeout = min(float(arguments.get("timeout_seconds", TIMEOUT_DEFAULT)), TIMEOUT_MAX)
        working_dir = arguments.get("working_dir") or os.getcwd()

        if not code:
            return [TextContent(type="text", text="❌ Error: Code is empty.")]

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

    elif name == "run_python_file":
        file_path = arguments.get("file_path", "")
        cli_args = [str(a) for a in arguments.get("args", [])]
        timeout = min(float(arguments.get("timeout_seconds", TIMEOUT_DEFAULT)), TIMEOUT_MAX)

        p = Path(file_path)
        if not p.exists():
            return [TextContent(type="text", text=f"❌ File not found: {file_path}")]

        stdout, stderr, rc = await loop.run_in_executor(
            _executor,
            _run_file_sync,
            get_python_exe(), str(p), cli_args, str(p.parent), timeout
        )
        return [TextContent(type="text", text=_format_result(stdout, stderr, rc, timeout))]

    elif name == "install_package":
        package = arguments.get("package_name", "").strip()
        if not package or any(c in package for c in [";", "&", "|", "`"]):
            return [TextContent(type="text", text="❌ Invalid package name.")]

        stdout, stderr, rc = await loop.run_in_executor(
            _executor, _install_sync, get_python_exe(), package
        )
        return [TextContent(type="text", text=_format_result(stdout, stderr, rc, 120))]

    else:
        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]


def _format_result(stdout: str, stderr: str, rc: int, timeout: float) -> str:
    if stderr.startswith("TIMEOUT:"):
        return f"⏱️ Timeout: Code execution exceeded {timeout}s limit."
    if stderr.startswith("ERROR:"):
        return f"❌ Error: {stderr[6:]}"

    parts = []
    if stdout:
        parts.append(f"📤 stdout:\n{stdout}")
    if stderr:
        parts.append(f"⚠️ stderr:\n{stderr}")
    if rc == 0:
        parts.append("✅ Exit code: 0" if (stdout or stderr) else "✅ Executed successfully (no output).")
    else:
        parts.append(f"❌ Exit code: {rc}")
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
