# Web Tools Implementation Plan

**Goal:** Add WebFetch and WebSearch tools so agents can access external information.

**Architecture:** Two new tools in `tools.py`: `web_fetch` (fetch URL content) and `web_search` (search via a search API). Both return text content to the agent.

---

### Task 1: Add web_fetch tool

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Add WebFetchTool**

After `IngestToKbTool`:

```python
class WebFetchTool(Tool):
    """Fetch content from a URL and return as text."""
    name = "web_fetch"
    description = "Fetch content from a URL and return it as text. Useful for reading documentation, APIs, and web pages."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "description": "Maximum characters to return (default 5000)"},
        },
        "required": ["url"],
    }

    def execute(self, url="", max_chars=5000, **kwargs) -> str:
        import urllib.request
        import urllib.error
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CocoCat/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                import re
                text = re.sub(r'<[^>]+>', '', content)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"
                return text
        except urllib.error.HTTPError as e:
            return f"HTTP error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return f"URL error: {e.reason}"
        except Exception as e:
            return f"Failed to fetch {url}: {e}"
```

- [ ] **Step 2: Register**

```python
    registry.register(WebFetchTool())
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: add web_fetch tool"
```

---

### Task 2: Add web_search tool

- [ ] **Step 1: Add WebSearchTool**

```python
class WebSearchTool(Tool):
    """Search the web using DuckDuckGo (no API key needed)."""
    name = "web_search"
    description = "Search the web for information. Returns a list of results with titles and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Maximum results (default 5)"},
        },
        "required": ["query"],
    }

    def execute(self, query="", max_results=5, **kwargs) -> str:
        import urllib.request
        import urllib.parse
        import json
        try:
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
            return "\n".join(results) if results else f"No results found for '{query}'."
        except Exception as e:
            return f"Search failed: {e}"
```

- [ ] **Step 2: Register**

```python
    registry.register(WebSearchTool())
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: add web_search tool (DuckDuckGo)"
```
