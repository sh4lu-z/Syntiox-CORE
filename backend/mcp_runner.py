import sys
import asyncio
from typing import Any, Dict
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def async_run_mcp_tool(server_script_path: str, tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Connects to a local MCP server script and calls a specific tool.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script_path],
        env=None
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return '\n'.join([c.text for c in result.content if hasattr(c, 'text')])
    except Exception as e:
        return f"MCP Execution Error: {str(e)}"

def run_mcp_tool(server_script_path: str, tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Synchronous wrapper to run an MCP tool from a local server.
    Usage:
        res = run_mcp_tool(r"D:\MCP\web_search_mcp.py", "search_web", {"query": "Sri Lanka"})
    """
    log_start = f"[ACTION_START] MCP Server: {tool_name}\n[ACTION_CMD] {tool_name}({arguments})\n"
    try:
        res = asyncio.run(async_run_mcp_tool(server_script_path, tool_name, arguments))
        return f"{log_start}{res}\n[ACTION_END]"
    except Exception as e:
        return f"{log_start}Error: {str(e)}\n[ACTION_END]"
