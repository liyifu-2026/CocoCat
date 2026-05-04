import urllib.request
import urllib.parse
import json
from ..base import SearchBackend


class DuckDuckGoSearch(SearchBackend):
    name = "duckduckgo"
    order = 30

    def search(self, query: str, max_results: int = 5) -> str:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "CocoCat/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        heading = data.get("Heading", "")
        abstract = data.get("AbstractText", "")
        if heading and abstract:
            results.append(f"## {heading}\n{abstract}\n")
        related = data.get("RelatedTopics", [])[:max_results]
        for r in related:
            if isinstance(r, dict):
                text = r.get("Text", "")
                url2 = r.get("FirstURL", "")
                if text:
                    results.append(f"- {text}\n  {url2}" if url2 else f"- {text}")
        if not results:
            return f"No results found for '{query}'."
        return "\n".join(results)
