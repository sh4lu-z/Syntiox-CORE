import os
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from googlesearch import search as google_search

# Load environment variables from .env
home_dir = os.path.expanduser("~")
data_dir = os.environ.get("SYNTIOX_DATA_DIR", os.path.join(home_dir, ".sh4lu-z", "Syntiox CORE"))
load_dotenv(os.path.join(data_dir, "config", ".env"))

# Initialize FastMCP server
mcp = FastMCP("web_tools_mcp")

@mcp.tool()
def read_url_content(url: str) -> str:
    """
    Reads the content of a URL and returns it as clean Markdown using BeautifulSoup and Markdownify.
    
    Args:
        url: The URL of the web page to read.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse HTML and convert to Markdown
        from bs4 import BeautifulSoup
        # pyrefly: ignore [missing-import]
        import markdownify
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script, style, and navigation elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript", "svg"]):
            element.decompose()
            
        # Try to find the main content area to avoid sidebars
        content_area = soup.find('article') or soup.find('main') or soup.find('div', id='content') or soup.find('div', class_='content') or soup.body or soup
            
        # Convert remaining HTML to markdown
        # Keep heading styles. We preserve links and images so the agent can navigate to related content.
        md_text = markdownify.markdownify(str(content_area), heading_style="ATX")
        
        # Clean up excessive newlines and spaces
        import re
        md_text = re.sub(r'\n{3,}', '\n\n', md_text).strip()
        md_text = re.sub(r' {3,}', '  ', md_text)
        
        # Add Title if available
        title = soup.title.string if soup.title else url
        final_md = f"# {title.strip()}\n\n{md_text}"
        
        if len(md_text) < 20:
            return "Failed to extract meaningful content from the page."
            
        return final_md
    except Exception as e:
        return f"Error reading URL: {str(e)}"

@mcp.tool()
def search_web(query: str) -> str:
    """
    Performs a web search for a given query.
    It returns a highly optimized, clean Markdown string to save AI tokens/characters.
    If all APIs fail, it falls back to a standard Google Search.
    
    Args:
        query: The search query string.
    """
    error_messages = []
    
    # 1. Try Tavily
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={"query": query, "api_key": tavily_key, "include_raw_content": False, "max_results": 5},
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for res in data.get('results', []):
                    title = res.get('title', 'No Title')
                    url = res.get('url', '')
                    content = res.get('content', '')
                    results.append(f"- [{title}]({url})\n  {content}")
                
                return f"🔍 Source: Tavily\n\n" + "\n\n".join(results)
            else:
                error_messages.append(f"Tavily Error: {response.status_code} - {response.text}")
        except Exception as e:
            error_messages.append(f"Tavily Exception: {str(e)}")
    else:
        error_messages.append("Tavily API key not found.")
        
    # 2. Try Exa
    exa_key = os.environ.get("EXA_API_KEY")
    if exa_key:
        try:
            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "x-api-key": exa_key
            }
            response = requests.post(
                "https://api.exa.ai/search",
                json={"query": query, "useAutoprompt": True, "numResults": 5, "contents": {"text": True}},
                headers=headers,
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for res in data.get('results', []):
                    title = res.get('title', 'No Title')
                    url = res.get('url', '')
                    text = res.get('text', '')[:300] + "..." if res.get('text') else ""
                    results.append(f"- [{title}]({url})\n  {text}")
                
                return f"🔍 Source: Exa\n\n" + "\n\n".join(results)
            else:
                error_messages.append(f"Exa Error: {response.status_code} - {response.text}")
        except Exception as e:
            error_messages.append(f"Exa Exception: {str(e)}")
    else:
        error_messages.append("Exa API key not found.")
        
    # 3. Try Firecrawl
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
    if firecrawl_key:
        try:
            headers = {
                "Authorization": f"Bearer {firecrawl_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(
                "https://api.firecrawl.dev/v1/search",
                json={"query": query, "limit": 5},
                headers=headers,
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                results = []
                for res in data.get('data', []):
                    title = res.get('title', 'No Title')
                    url = res.get('url', '')
                    desc = res.get('markdown', '')[:300] + "..." if res.get('markdown') else ""
                    results.append(f"- [{title}]({url})\n  {desc}")
                
                return f"🔍 Source: Firecrawl\n\n" + "\n\n".join(results)
            else:
                error_messages.append(f"Firecrawl Error: {response.status_code} - {response.text}")
        except Exception as e:
            error_messages.append(f"Firecrawl Exception: {str(e)}")
    else:
        error_messages.append("Firecrawl API key not found.")
        
    # 4. Try Google Search Fallback
    try:
        google_results = []
        for j in google_search(query, num_results=5, sleep_interval=2):
            google_results.append(f"- {j}")
        if google_results:
            return f"🔍 Source: Google Search Fallback\n\n" + "\n".join(google_results)
    except Exception as e:
        error_messages.append(f"Google Fallback Exception: {str(e)}")
        
    # If all failed
    return "❌ Web search failed across all providers.\nErrors:\n" + "\n".join(error_messages)

if __name__ == "__main__":
    mcp.run()
