"""Test browser tool — Playwright headless browser automation."""
import os
import tempfile
import pytest
from cococat.core.tools import resolve_tools_for_mode, ToolRegistry
from cococat.core.tools.execution import make_execution_tools


def _browser_tools():
    return resolve_tools_for_mode("kb-admin") + make_execution_tools(None)


class TestBrowser:
    @pytest.mark.asyncio
    async def test_navigate_and_return_page_text(self):
        """browser tool navigates to a URL and returns page text content."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        html = "<html><body><h1>Hello Browser</h1><p>Test page content</p></body></html>"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            tmp_path = f.name

        try:
            url = "file://" + tmp_path
            result = await reg.execute("browser", {
                "action": f'{{"type":"navigate","url":"{url}"}}',
            })

            assert "Hello Browser" in result
            assert "Test page content" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_browser_handles_invalid_url(self):
        """browser tool returns error or empty page for unreachable URL."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("browser", {
            "action": '{"type":"navigate","url":"http://127.0.0.1:1"}',
        })

        assert "error" in result.lower() or "Error" in result or "Title:" in result

    @pytest.mark.asyncio
    async def test_browser_requires_action(self):
        """browser tool returns error when no action provided."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("browser", {})
        assert "error" in result.lower() or "action" in result.lower()

    @pytest.mark.asyncio
    async def test_browser_handles_invalid_json_action(self):
        """browser tool handles malformed JSON in action parameter."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("browser", {"action": "not json"})
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_click_by_selector(self):
        """browser tool clicks an element by CSS selector (navigates first via url param)."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        html = "<html><body><button id='btn'>Click Me</button></body></html>"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            tmp_path = f.name

        try:
            url = "file://" + tmp_path
            result = await reg.execute("browser", {
                "action": f'{{"type":"click","url":"{url}","selector":"#btn"}}',
            })
            assert "Clicked" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_type_into_input(self):
        """browser tool types text into an input field (navigates first via url param)."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        html = '<html><body><input id="name" type="text"></body></html>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            tmp_path = f.name

        try:
            url = "file://" + tmp_path
            result = await reg.execute("browser", {
                "action": f'{{"type":"type","url":"{url}","selector":"#name","text":"hello"}}',
            })
            assert "Typed into '#name'" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_scroll_down(self):
        """browser tool scrolls the page (navigates first via url param)."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        html = '<html><body style="height:2000px"><p>top</p></body></html>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            tmp_path = f.name

        try:
            url = "file://" + tmp_path
            result = await reg.execute("browser", {
                "action": f'{{"type":"scroll","url":"{url}","direction":"down","amount":500}}',
            })
            assert "Scrolled down" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_execute_js(self):
        """browser tool executes JavaScript on the page (navigates first via url param)."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        html = "<html><body><p>test</p></body></html>"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            tmp_path = f.name

        try:
            url = "file://" + tmp_path
            result = await reg.execute("browser", {
                "action": f'{{"type":"execute_js","url":"{url}","code":"document.title"}}',
            })
            assert "Error" not in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_go_back(self):
        """browser tool navigates back in history (url param loads the second page first)."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        html1 = "<html><body><h1>Page 1</h1></body></html>"
        html2 = "<html><body><h1>Page 2</h1></body></html>"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html1)
            tmp_path1 = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html2)
            tmp_path2 = f.name

        try:
            url1 = "file://" + tmp_path1
            url2 = "file://" + tmp_path2
            result1 = await reg.execute("browser", {"action": f'{{"type":"navigate","url":"{url1}"}}'})
            assert "Page 1" in result1 or "Error" not in result1
            result2 = await reg.execute("browser", {"action": f'{{"type":"navigate","url":"{url2}"}}'})
            assert "Page 2" in result2 or "Error" not in result2
            result = await reg.execute("browser", {"action": '{"type":"go_back"}'})
            assert "[Back]" in result
        finally:
            os.unlink(tmp_path1)
            os.unlink(tmp_path2)

    @pytest.mark.asyncio
    async def test_click_requires_selector(self):
        """browser click returns error when selector is missing."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("browser", {
            "action": '{"type":"click"}',
        })
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_type_requires_selector(self):
        """browser type returns error when selector is missing."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("browser", {
            "action": '{"type":"type","text":"hello"}',
        })
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_browser_unknown_action(self):
        """browser tool returns error for unknown action type."""
        tools = _browser_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("browser", {
            "action": '{"type":"fly_to_moon"}',
        })
        assert "unknown action type" in result.lower() or "Error" in result
