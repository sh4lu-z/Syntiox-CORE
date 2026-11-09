"""
📰 Google News Handler Tools (RSS - No OAuth needed)
"""
import xml.etree.ElementTree as ET
import requests
from mcp.server.fastmcp import FastMCP

# 1. ස්වාධීන FastMCP සර්වර් එකක් සෑදීම
mcp = FastMCP("Google-News-Tools")

CATEGORIES = {
    "top"          : "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    "technology"   : "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGxqTjNjd1NHdGlkR1J5TlRBQVAB?hl=en-US&gl=US&ceid=US:en",
    "business"     : "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlBQVAB?hl=en-US&gl=US&ceid=US:en",
    "sports"       : "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pWVXlBQVAB?hl=en-US&gl=US&ceid=US:en",
    "entertainment": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pWVXlBQVAB?hl=en-US&gl=US&ceid=US:en",
    "health"       : "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ?hl=en-US&gl=US&ceid=US:en",
    "world"        : "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlBQVAB?hl=en-US&gl=US&ceid=US:en",
    "science"      : "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0YVhjU0FtVnVHZ0pWVXlBQVAB?hl=en-US&gl=US&ceid=US:en",
}


def _parse_rss(url: str, max_items: int = 10) -> list[dict]:
    resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
    root = ET.fromstring(resp.content)
    ns   = {'media': 'http://search.yahoo.com/mrss/'}
    items = []
    for item in root.findall('.//item')[:max_items]:
        title  = item.findtext('title', '').strip()
        link   = item.findtext('link', '').strip()
        pub    = item.findtext('pubDate', '').strip()
        source = item.findtext('source', '').strip()
        # Clean title - remove " - Source" suffix added by Google News
        if ' - ' in title:
            parts  = title.rsplit(' - ', 1)
            title  = parts[0].strip()
            source = source or parts[1].strip()
        items.append({'title': title, 'link': link, 'pubDate': pub, 'source': source})
    return items


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 1: Top News
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def get_google_top_news(max_results: int = 10) -> str:
    """Get Google News Top Stories."""
    try:
        items  = _parse_rss(CATEGORIES["top"], max_results)
        output = f"📰 GOOGLE NEWS — TOP {len(items)} STORIES\n{'─'*45}\n"
        for i, n in enumerate(items, 1):
            output += (
                f"{i:02}. 🔵 {n['title']}\n"
                f"     📡 {n['source']} | 🕐 {n['pubDate'][:25]}\n"
                f"     🔗 {n['link']}\n"
                f"{'─'*45}\n"
            )
        return output
    except Exception as e:
        return f"❌ Error fetching Google News: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 2: Search Google News
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def search_google_news(query: str, max_results: int = 8) -> str:
    """Search Google News using keywords."""
    try:
        url    = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        items  = _parse_rss(url, max_results)
        if not items:
            return f"🔍 No news found for '{query}'."
        output = f"🔍 GOOGLE NEWS: '{query}' — {len(items)} RESULTS\n{'─'*45}\n"
        for i, n in enumerate(items, 1):
            output += (
                f"{i:02}. 🔵 {n['title']}\n"
                f"     📡 {n['source']} | 🕐 {n['pubDate'][:25]}\n"
                f"     🔗 {n['link']}\n"
                f"{'─'*45}\n"
            )
        return output
    except Exception as e:
        return f"❌ Error searching news: {e}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOOL 3: News by Category
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@mcp.tool()
def get_google_news_by_category(category: str, max_results: int = 8) -> str:
    """
    Google News category අනුව ලබාගනී.
    Use when user asks for specific category news.
    Available categories: top, technology, business, sports, entertainment, health, world, science
    """
    cat = category.lower().strip()
    if cat not in CATEGORIES:
        return (
            f"❌ Category '{category}' not found.\n"
            f"📋 Available: {', '.join(CATEGORIES.keys())}"
        )
    try:
        emoji_map = {
            "top":"🌍","technology":"💻","business":"💼","sports":"⚽",
            "entertainment":"🎬","health":"🏥","world":"🌐","science":"🔬"
        }
        items  = _parse_rss(CATEGORIES[cat], max_results)
        output = f"{emoji_map.get(cat,'📰')} GOOGLE NEWS — {cat.upper()}\n{'─'*45}\n"
        for i, n in enumerate(items, 1):
            output += (
                f"{i:02}. 🔵 {n['title']}\n"
                f"     📡 {n['source']} | 🕐 {n['pubDate'][:25]}\n"
                f"{'─'*45}\n"
            )
        return output
    except Exception as e:
        return f"❌ Error fetching category news: {e}"


# ──────────────────────────────────────────────────────────────
# ▶️ Entry Point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport='stdio')