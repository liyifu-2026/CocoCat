"""Test read_file tool via ToolRegistry public interface."""
import pytest


@pytest.mark.asyncio
async def test_read_file_returns_content(registry, tmp_file):
    path, expected = tmp_file
    result = await registry.execute("read_file", {"path": path})
    assert result == expected


@pytest.mark.asyncio
async def test_read_file_with_offset(registry, tmp_file):
    path, _ = tmp_file
    result = await registry.execute("read_file", {"path": path, "offset": 1})
    assert result == "line 2\nline 3\n"


@pytest.mark.asyncio
async def test_read_file_with_limit(registry, tmp_file):
    path, _ = tmp_file
    result = await registry.execute("read_file", {"path": path, "limit": 2})
    assert result == "hello world\nline 2\n"


@pytest.mark.asyncio
async def test_read_file_nonexistent(registry):
    result = await registry.execute("read_file", {"path": "/nonexistent/file.txt"})
    assert "Error" in result


@pytest.mark.asyncio
async def test_read_file_unknown_tool(registry):
    with pytest.raises(ValueError, match="Unknown tool"):
        await registry.execute("nonexistent_tool", {})
