import html as html_mod
import urllib.request
import urllib.parse
import re
from ..base import SearchBackend


class BingSearch(SearchBackend):
    name = "bing"
    order = 20

    def search(self, query: str, max_results: int = 5) -> str:
        encoded = urllib.parse.quote(query)
        url = f"https://cn.bing.com/search?q={encoded}&count={max_results}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = []
        blocks = re.findall(
            r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>',
            html, re.DOTALL,
        )

        for block in blocks[:max_results]:
            # Extract title from <a> tag
            title_match = re.search(r'<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>', block, re.DOTALL)
            title = title_match.group(2).strip() if title_match else ""
            link = title_match.group(1).strip() if title_match else ""
            title = re.sub(r'<[^>]+>', '', title).strip()
            # Extract snippet from <p> tag
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
            snippet = re.sub(r'\s+', ' ', snippet)
            if title:
                line = f"- {html_mod.unescape(title)}"
                if link:
                    line += f"\n  {link}"
                if snippet:
                    line += f"\n  {html_mod.unescape(snippet[:300])}"
                results.append(line)

        if not results:
            snippets = re.findall(
                r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>',
                html, re.DOTALL,
            )
            for s in snippets[:max_results]:
                text = re.sub(r'<[^>]+>', '', s).strip()
                if text:
                    results.append(f"- {text}")

        if not results:
            return f"No results found for '{query}'."
        return "\n".join(results)
