"""Test pin/unpin memory tools."""
import pytest
import os


@pytest.fixture
def memory_file(tmp_path):
    path = tmp_path / "memory.md"
    path.write_text("existing fact\n")
    return str(path)


@pytest.mark.asyncio
async def test_pin_appends_fact(registry, memory_file):
    ctx = {"memory_path": memory_file}
    result = await registry.execute("pin", {"fact": "user prefers dark mode"}, ctx)
    assert "pinned" in result.lower()
    content = open(memory_file).read()
    assert "user prefers dark mode" in content
    assert "existing fact" in content


@pytest.mark.asyncio
async def test_pin_appends_multiple_facts(registry, memory_file):
    ctx = {"memory_path": memory_file}
    await registry.execute("pin", {"fact": "fact one"}, ctx)
    await registry.execute("pin", {"fact": "fact two"}, ctx)
    content = open(memory_file).read()
    assert content.count("fact one") == 1
    assert content.count("fact two") == 1


@pytest.mark.asyncio
async def test_unpin_removes_by_keyword(registry, memory_file):
    ctx = {"memory_path": memory_file}
    await registry.execute("pin", {"fact": "user likes python"}, ctx)
    await registry.execute("pin", {"fact": "user likes java"}, ctx)
    result = await registry.execute("unpin", {"keyword": "java"}, ctx)
    assert "unpinned" in result.lower()
    content = open(memory_file).read()
    assert "user likes python" in content
    assert "java" not in content


@pytest.mark.asyncio
async def test_unpin_nonexistent_keyword(registry, memory_file):
    ctx = {"memory_path": memory_file}
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
