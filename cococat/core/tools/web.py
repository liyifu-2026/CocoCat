"""Web tools — search and fetch."""

from cococat.core.types import ToolContext, WebEnv

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


def _web_search(query: str, ctx: ToolContext) -> str:
    if not query:
        return "Error: 'query' is required"
    api_key = ctx.web.tavily_api_key
    if not api_key:
        return ("Web search requires a search API key (e.g. Tavily, SerpAPI). "
                f"Configure it to enable live search. Query was: {query}")
    if TavilyClient is None:
        return "Error: tavily-python package not installed. Run: pip install tavily-python"
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=5)
        results = response.get("results", [])
        if not results:
            return f"No results found for: {query}"
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            content = r.get("content", "")
            lines.append(f"{i}. {title}\n   {url}\n   {content[:200]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Error searching '{query}': {e}"


def _web_fetch(url: str) -> str:
    if not url:
        return "Error: 'url' is required"
    import httpx
    try:
        resp = httpx.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        text = resp.text
        return text[:5000] + ("..." if len(text) > 5000 else "")
    except httpx.TimeoutException:
        return "Error: request timed out"
    except Exception as e:
        return f"Error fetching {url}: {e}"


def make_web_tools(tavily_api_key=None) -> dict:
    from cococat.core.tools.types import Tool, _with_env
    return {
        "web_search": Tool(name="web_search", description="Search the web",
             parameters={"query": "string"},
             execute=lambda p, ctx: _web_search(p.get("query", ""), _with_env(ctx, web=WebEnv(tavily_api_key=tavily_api_key)))),
        "web_fetch": Tool(name="web_fetch", description="Fetch URL content",
             parameters={"url": "string"},
             execute=lambda p, ctx: _web_fetch(p.get("url", ""))),
    }
