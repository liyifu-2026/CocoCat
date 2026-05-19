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
             "sub_agent", "check_tasks", "stop_task",
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


@pytest.mark.asyncio
async def test_edit_file_success(tmp_dir):
    test_file = os.path.join(tmp_dir, "edit.md")
    with open(test_file, "w") as f:
        f.write("Hello World")

    tools = create_core_tools()
    reg = ToolRegistry(tools)
    result = await reg.execute("edit_file", {"path": test_file, "old": "World", "new": "CocoCat"})
    assert "Edit" in result
    with open(test_file) as f:
        assert f.read() == "Hello CocoCat"


@pytest.mark.asyncio
async def test_edit_file_not_found(tmp_dir):
    test_file = os.path.join(tmp_dir, "edit.md")
    with open(test_file, "w") as f:
        f.write("Hello World")

    tools = create_core_tools()
    reg = ToolRegistry(tools)
    result = await reg.execute("edit_file", {"path": test_file, "old": "NotFound", "new": "X"})
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_list_dir_with_files(tmp_dir):
    tools = create_core_tools()
    reg = ToolRegistry(tools)
    result = await reg.execute("list_dir", {"path": tmp_dir})
    assert "test.md" not in result and isinstance(result, str)


@pytest.mark.asyncio
async def test_list_dir_nonexistent():
    tools = create_core_tools()
    reg = ToolRegistry(tools)
    result = await reg.execute("list_dir", {"path": "/nonexistent_dir_xyz"})
    assert "Error" in result


@pytest.mark.asyncio
async def test_edit_file_nonexistent(tmp_dir):
    tools = create_core_tools()
    reg = ToolRegistry(tools)
    result = await reg.execute("edit_file", {"path": os.path.join(tmp_dir, "nope.md"), "old": "x", "new": "y"})
    assert "Error" in result
