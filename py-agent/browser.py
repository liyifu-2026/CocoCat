import os
import re
from dataclasses import dataclass


@dataclass
class PageState:
    url: str = ""
    title: str = ""
    content_length: int = 0


class BrowserSession:
    """Manages a single browser page session."""

    def __init__(self):
        self._page = None
        self._browser = None

    def _ensure(self):
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        self._browser = p.chromium.launch(headless=True)
        self._page = self._browser.new_page()
        self._page.set_default_timeout(15000)

    def navigate(self, url: str) -> str:
        self._ensure()
        self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_load_state("networkidle")
        title = self._page.title()
        text = self._page.inner_text("body")[:5000]
        return f"Title: {title}\nURL: {self._page.url}\n\nContent:\n{text}"

    def click(self, selector: str) -> str:
        self._ensure()
        self._page.click(selector)
        self._page.wait_for_load_state("networkidle")
        return f"Clicked: {selector}"

    def fill(self, selector: str, value: str) -> str:
        self._ensure()
        self._page.fill(selector, value)
        return f"Filled {selector}: {value}"

    def extract(self, selector: str = "body") -> str:
        self._ensure()
        elements = self._page.query_selector_all(selector)
        if not elements:
            return f"No elements matched '{selector}'"
        results = []
        for el in elements[:10]:
            text = el.inner_text()[:500]
            if text.strip():
                results.append(text)
        return "\n\n---\n\n".join(results) if results else f"No text found in '{selector}'"

    def screenshot(self, path: str) -> str:
        self._ensure()
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        self._page.screenshot(path=path, full_page=True)
        return f"Screenshot saved to {path}"

    def scroll(self, direction: str = "down") -> str:
        self._ensure()
        delta = 800 if direction == "down" else -800
        self._page.evaluate(f"window.scrollBy(0, {delta})")
        self._page.wait_for_timeout(500)
        return f"Scrolled {direction}"

    def get_links(self) -> str:
        self._ensure()
        links = self._page.query_selector_all("a[href]")
        results = []
        for el in links[:30]:
            href = el.get_attribute("href") or ""
            text = el.inner_text()[:60]
            if href and text and not href.startswith("#"):
                results.append(f"- {text}: {href}")
        return "\n".join(results) if results else "(no links found)"

    def close(self):
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
