"""Test web tools: web_fetch, web_search."""
import pytest
from unittest.mock import patch, MagicMock
from cococat.core.tools import create_core_tools, ToolRegistry


class TestWebFetch:
    @pytest.mark.asyncio
    async def test_web_fetch_missing_url(self, registry):
        result = await registry.execute("web_fetch", {})
        assert "required" in result.lower() or "url" in result.lower()

    @pytest.mark.asyncio
    async def test_web_fetch_invalid_url(self, registry):
        result = await registry.execute("web_fetch", {"url": "not-a-valid-url"})
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_web_fetch_nonexistent_host(self, registry):
        result = await registry.execute("web_fetch", {"url": "http://nonexistent.example.test"})
        assert "error" in result.lower()


class TestWebSearch:
    @pytest.mark.asyncio
    async def test_web_search_returns_hint(self, registry):
        result = await registry.execute("web_search", {"query": "test"})
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_web_search_missing_query(self, registry):
        result = await registry.execute("web_search", {})
        assert "required" in result.lower() or "query" in result.lower()

    @pytest.mark.asyncio
    async def test_web_search_calls_tavily_with_api_key(self):
        """When tavily_api_key is configured, web_search calls Tavily and returns results."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [
                {"title": "Python Tutorial", "url": "https://example.com", "content": "Learn Python"}
            ]
        }

        with patch("cococat.core.tools.TavilyClient", return_value=mock_client):
            tools = create_core_tools(tavily_api_key="tvly-test-key")
            reg = ToolRegistry(tools)

            result = await reg.execute("web_search", {"query": "python"})

        # Should NOT return the hint message
        assert "requires a search API key" not in result
        assert "Python Tutorial" in result

    @pytest.mark.asyncio
    async def test_web_search_handles_tavily_error(self):
        """web_search handles Tavily errors gracefully."""
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API rate limited")

        with patch("cococat.core.tools.TavilyClient", return_value=mock_client):
            tools = create_core_tools(tavily_api_key="tvly-bad-key")
            reg = ToolRegistry(tools)

            result = await reg.execute("web_search", {"query": "test"})

        assert "error" in result.lower()
