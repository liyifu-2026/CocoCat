import urllib.request
import urllib.parse
import re
from ..base import SearchBackend


class BaiduSearch(SearchBackend):
    name = "baidu"
    order = 10

    def search(self, query: str, max_results: int = 5) -> str:
        encoded = urllib.parse.quote(query)
        url = f"https://www.baidu.com/s?wd={encoded}&rn={max_results}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Baidu returns a blocking page when bot-detected (short HTML, no real content)
        if len(html) < 5000 or "result" not in html.lower():
            raise ConnectionError("Baidu returned bot-blocking page or unavailable")

        results = []
        blocks = re.findall(
            r'<div[^>]*class="[^"]*c-abstract[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL,
        )
        if not blocks:
            blocks = re.findall(
                r'<span[^>]*class="[^"]*content-right[^"]*"[^>]*>(.*?)</span>',
                html, re.DOTALL,
            )
        if not blocks:
            blocks = re.findall(
                r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>',
                html, re.DOTALL,
            )

        for block in blocks[:max_results]:
            text = re.sub(r'<[^>]+>', '', block).strip()
            text = re.sub(r'\s+', ' ', text)
            if text and len(text) > 10:
                results.append(f"- {text[:300]}")

        if not results:
            titles = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
            for t in titles[:max_results]:
                text = re.sub(r'<[^>]+>', '', t).strip()
                if text:
                    results.append(f"- {text}")

        if not results:
            return f"No results found for '{query}'."
        return "\n".join(results)
