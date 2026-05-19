"""Test pin/unpin memory tools on pinned.md."""
import os
import pytest


@pytest.fixture
def agent_dir(tmp_path):
    path = str(tmp_path / "test-agent")
    os.makedirs(path, exist_ok=True)
    return path


@pytest.mark.asyncio
async def test_pin_appends_fact(registry, agent_dir):
    ctx = {"agent_dir": agent_dir}
    result = await registry.execute("pin", {"fact": "user prefers dark mode"}, ctx)
    assert "pinned" in result.lower()
    content = open(os.path.join(agent_dir, "pinned.md")).read()
    assert "user prefers dark mode" in content


@pytest.mark.asyncio
async def test_pin_appends_multiple_facts(registry, agent_dir):
    ctx = {"agent_dir": agent_dir}
    await registry.execute("pin", {"fact": "fact one"}, ctx)
    await registry.execute("pin", {"fact": "fact two"}, ctx)
    content = open(os.path.join(agent_dir, "pinned.md")).read()
    assert "fact one" in content
    assert "fact two" in content


@pytest.mark.asyncio
async def test_unpin_removes_by_keyword(registry, agent_dir):
    ctx = {"agent_dir": agent_dir}
    await registry.execute("pin", {"fact": "user likes python"}, ctx)
    await registry.execute("pin", {"fact": "user likes java"}, ctx)
    result = await registry.execute("unpin", {"keyword": "java"}, ctx)
    assert "unpinned" in result.lower()
    content = open(os.path.join(agent_dir, "pinned.md")).read()
    assert "python" in content
    assert "java" not in content


@pytest.mark.asyncio
async def test_unpin_nonexistent_keyword(registry, agent_dir):
    ctx = {"agent_dir": agent_dir}
    result = await registry.execute("unpin", {"keyword": "nonexistent"}, ctx)
    assert "not found" in result.lower() or "no facts" in result.lower()


@pytest.mark.asyncio
async def test_pin_missing_fact(registry):
    result = await registry.execute("pin", {})
    assert "required" in result.lower()


@pytest.mark.asyncio
async def test_unpin_missing_keyword(registry):
    result = await registry.execute("unpin", {})
    assert "required" in result.lower()
