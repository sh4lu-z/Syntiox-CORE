import os
import re
import requests
from dotenv import load_dotenv
from tools.logger import action_logger

try:
    from backend.config_paths import ENV_FILE
    load_dotenv(ENV_FILE)
except Exception:
    load_dotenv()

@action_logger("search_web")
def search_web(query: str) -> str:
    """
    Searches the live internet for a given query using Tavily, Exa, or Firecrawl.
    Returns a markdown string with titles, URLs, and descriptions of the results.
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

                if results:
                    return "Source: Tavily\n\n" + "\n\n".join(results)
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

                if results:
                    return "Source: Exa\n\n" + "\n\n".join(results)
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

                if results:
                    return "Source: Firecrawl\n\n" + "\n\n".join(results)
            else:
                error_messages.append(f"Firecrawl Error: {response.status_code} - {response.text}")
        except Exception as e:
            error_messages.append(f"Firecrawl Exception: {str(e)}")
    else:
        error_messages.append("Firecrawl API key not found.")

    return "Web search failed across all providers.\nErrors:\n" + "\n".join(error_messages)

@action_logger("read_url_content")
def read_url_content(url: str) -> str:
    """
    Fetches the content of a specific webpage URL and converts it to markdown.
    Use this to read articles, documentation, or search result links.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        from bs4 import BeautifulSoup
        import markdownify

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script, style, and navigation elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript", "svg"]):
            element.decompose()

        # Find main content area
        content_area = soup.find('article') or soup.find('main') or soup.find('div', id='content') or soup.find('div', class_='content') or soup.body or soup

        # Convert remaining HTML to markdown
        md_text = markdownify.markdownify(str(content_area), heading_style="ATX")

        # Clean up excessive newlines and spaces
        md_text = re.sub(r'\n{3,}', '\n\n', md_text).strip()
        md_text = re.sub(r' {3,}', '  ', md_text)

        title = soup.title.get_text(strip=True) if soup.title else url
        final_md = f"# {title}\n\n{md_text}"

        if len(md_text) < 20:
            return "Failed to extract meaningful content from the page."

        return final_md
    except Exception as e:
        return f"Error reading URL: {str(e)}"
