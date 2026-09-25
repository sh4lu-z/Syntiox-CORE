import os
from backend.mcp_runner import run_mcp_tool
from TOOLS.core.logger import action_logger

def _run_google_news_mcp(tool_name: str, args: dict):
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(root_dir, "MCP", "google", "google_news_handlers.py")
    return run_mcp_tool(server_path, tool_name, args)

@action_logger("get_google_top_news")
def get_google_top_news(max_results: int = 10) -> str:
    """Get Google News Top Stories."""
    return _run_google_news_mcp("get_google_top_news", {"max_results": max_results})

@action_logger("search_google_news")
def search_google_news(query: str, max_results: int = 8) -> str:
    """Search Google News using keywords."""
    return _run_google_news_mcp("search_google_news", {"query": query, "max_results": max_results})

@action_logger("get_google_news_by_category")
def get_google_news_by_category(category: str, max_results: int = 8) -> str:
    """Google News category අනුව ලබාගනී.
Use when user asks for specific category news.
Available categories: top, technology, business, sports, entertainment, health, world, science"""
    return _run_google_news_mcp("get_google_news_by_category", {"category": category, "max_results": max_results})
