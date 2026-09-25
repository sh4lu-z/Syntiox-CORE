import os
from TOOLS.core.logger import action_logger

@action_logger("search_web")
def search_web(query: str) -> str:
    """
    Searches the live internet for a given query.
    Returns a markdown string with titles, URLs, and descriptions of the results.
    """
    from backend.mcp_runner import run_mcp_tool
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "web_search_mcp.py")
    
    return run_mcp_tool(server_path, "search_web", {"query": query})

@action_logger("read_url_content")
def read_url_content(url: str) -> str:
    """
    Fetches the content of a specific webpage URL and converts it to markdown.
    Use this to read articles, documentation, or search result links.
    """
    from backend.mcp_runner import run_mcp_tool
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "web_search_mcp.py")
    
    return run_mcp_tool(server_path, "read_url_content", {"url": url})
