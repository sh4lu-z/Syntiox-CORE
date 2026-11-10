import json
from tools.core.logger import action_logger
from backend.mcp_runner import call_mcp_server_tool

@action_logger("call_mcp_tool")
def call_mcp_tool(server_name: str, tool_name: str, arguments: dict = None) -> str:
    """
    Call a lazy-loaded MCP tool from an MCP server.
    Before calling an MCP tool, read its JSON schema file in mcp_schemas/<server_name>/<tool_name>.json using view_file to verify its exact arguments.
    """
    if arguments is None:
        parsed_args = {}
    elif isinstance(arguments, str):
        try:
            parsed_args = json.loads(arguments)
        except Exception:
            parsed_args = {}
    elif isinstance(arguments, dict):
        parsed_args = dict(arguments)
    else:
        parsed_args = {}
    parsed_args.pop("requires_approval", None)
    return call_mcp_server_tool(server_name, tool_name, parsed_args)
