"""Tests for cococat.core.tools."""
import os
import tempfile
import pytest
from cococat.core.tools import ToolRegistry, create_core_tools


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.mark.asyncio
async def test_core_tools_all_present():
    tools = create_core_tools()
    names = {t["name"] for t in tools}
    core = {"read_file", "write_file", "edit_file", "list_dir", "bash",
            "glob", "grep", "web_search", "web_fetch", "browser",
            "sub_agent", "check_tasks", "stop_task", "todo_write",
            "recall", "pin", "unpin", "record_experience", "recall_experience",
            "cron", "current_status", "wait"}
    assert core.issubset(names)


@pytest.mark.asyncio
async def test_tool_registry_execute(tmp_dir):
    tools = create_core_tools()
    reg = ToolRegistry(tools)

    result = await reg.execute("read_file", {"path": __file__})
    assert "cococat" in result or "test_tools" in result


@pytest.mark.asyncio
async def test_tool_registry_unknown_tool():
    reg = ToolRegistry([])
    with pytest.raises(ValueError, match="Unknown tool"):
        await reg.execute("nonexistent", {})


@pytest.mark.asyncio
async def test_tool_filter_by_permission():
    tools = create_core_tools()
    reg = ToolRegistry(tools)

    # Filter to file tools only
    file_tools = reg.filter({"read_file", "write_file", "bash"})
    names = {t["name"] for t in file_tools}
    assert names == {"read_file", "write_file", "bash"}


@pytest.mark.asyncio
async def test_read_file_returns_content(tmp_dir):
    test_file = os.path.join(tmp_dir, "test.md")
    with open(test_file, "w") as f:
        f.write("Hello World")

    tools = create_core_tools()
    reg = ToolRegistry(tools)
    result = await reg.execute("read_file", {"path": test_file})
    assert "Hello World" in result


@pytest.mark.asyncio
async def test_write_file_creates_file(tmp_dir):
    test_file = os.path.join(tmp_dir, "new.md")
    tools = create_core_tools()
    reg = ToolRegistry(tools)
    result = await reg.execute("write_file", {"path": test_file, "content": "New content"})
    assert os.path.exists(test_file)
    with open(test_file) as f:
        assert f.read() == "New content"


@pytest.mark.asyncio
async def test_list_tools():
    tools = create_core_tools()
    reg = ToolRegistry(tools)
    all_tools = reg.list_tools()
    names = {t["name"] for t in all_tools}
    assert "read_file" in names
    assert "bash" in names
    assert "cron" in names
    assert len(all_tools) == len(tools)
