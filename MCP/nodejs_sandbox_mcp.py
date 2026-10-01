#!/usr/bin/env python3
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
"""
NodeJS Code Sandbox MCP Server - Windows Compatible
"""

import asyncio
import subprocess
import tempfile
import os
import textwrap
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("nodejs-sandbox")

TIMEOUT_DEFAULT = 15
TIMEOUT_MAX     = 60

_executor = ThreadPoolExecutor(max_workers=4)

def get_node_exe() -> str:
    """Finds the node executable."""
    node_exe = shutil.which("node")
    if not node_exe:
        raise RuntimeError("NodeJS is not installed or not found in PATH.")
    return node_exe

def get_npm_exe() -> str:
    """Finds the npm executable."""
    npm_exe = shutil.which("npm")
    if not npm_exe:
        if os.name == 'nt':
            npm_exe = shutil.which("npm.cmd")
        if not npm_exe:
            raise RuntimeError("npm is not installed or not found in PATH.")
    return npm_exe

def _run_code_sync(node_exe: str, script_path: str, cwd: str, timeout: float) -> tuple[str, str, int]:
    """Synchronous subprocess run - Windows compatible."""
    try:
        result = subprocess.run(
            [node_exe, script_path],
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

def _run_file_sync(node_exe: str, file_path: str, cli_args: list, cwd: str, timeout: float) -> tuple[str, str, int]:
    try:
        result = subprocess.run(
            [node_exe, file_path] + cli_args,
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

def _install_sync(npm_exe: str, package: str, cwd: str) -> tuple[str, str, int]:
    try:
        result = subprocess.run(
            [npm_exe, "install", package],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT:120", -1
    except Exception as e:
        return "", f"ERROR:{e}", -1

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="run_nodejs",
            description="Executes a NodeJS snippet and returns stdout/stderr.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "timeout_seconds": {"type": "number", "default": TIMEOUT_DEFAULT},
                    "working_dir": {"type": "string", "description": "Absolute path to the working directory."}
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="run_nodejs_file",
            description="Executes a .js file and returns output.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "args": {"type": "array", "items": {"type": "string"}},
                    "timeout_seconds": {"type": "number", "default": TIMEOUT_DEFAULT}
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="install_npm_package",
            description="Installs an npm package in the specified directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "package_name": {"type": "string"},
                    "working_dir": {"type": "string", "description": "Absolute path to the project directory where package.json/node_modules resides."}
                },
                "required": ["package_name", "working_dir"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    loop = asyncio.get_running_loop()

    try:
        node_exe = get_node_exe()
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Initialization Error: {e}")]

    if name == "run_nodejs":
        code = arguments.get("code", "")
        timeout = min(float(arguments.get("timeout_seconds", TIMEOUT_DEFAULT)), TIMEOUT_MAX)
        cwd = arguments.get("working_dir") or str(Path.home())

        if not os.path.exists(cwd):
            return [TextContent(type="text", text=f"❌ Error: Working directory '{cwd}' does not exist.")]

        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8')
        try:
            tmp.write(code)
            tmp.close()

            stdout, stderr, rc = await loop.run_in_executor(
                _executor,
                _run_code_sync,
                node_exe, tmp.name, cwd, timeout
            )
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        return [TextContent(type="text", text=_format_result(stdout, stderr, rc, timeout))]

    elif name == "run_nodejs_file":
        file_path = arguments.get("file_path", "")
        cli_args = [str(a) for a in arguments.get("args", [])]
        timeout = min(float(arguments.get("timeout_seconds", TIMEOUT_DEFAULT)), TIMEOUT_MAX)

        p = Path(file_path)
        if not p.exists():
            return [TextContent(type="text", text=f"❌ File not found: {file_path}")]

        stdout, stderr, rc = await loop.run_in_executor(
            _executor,
            _run_file_sync,
            node_exe, str(p), cli_args, str(p.parent), timeout
        )
        return [TextContent(type="text", text=_format_result(stdout, stderr, rc, timeout))]

    elif name == "install_npm_package":
        package = arguments.get("package_name", "").strip()
        cwd = arguments.get("working_dir")
        
        if not cwd or not os.path.exists(cwd):
            return [TextContent(type="text", text=f"❌ Error: Working directory '{cwd}' does not exist. Cannot install npm packages globally.")]

        if not package or any(c in package for c in [";", "&", "|", "`"]) or package.startswith("-"):
            return [TextContent(type="text", text="❌ Invalid package name.")]

        try:
            npm_exe = get_npm_exe()
        except Exception as e:
             return [TextContent(type="text", text=f"❌ Initialization Error: {e}")]

        stdout, stderr, rc = await loop.run_in_executor(
            _executor, _install_sync, npm_exe, package, cwd
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
