"""Test memory search: recall."""
import pytest
import os


class TestRecall:
    @pytest.mark.asyncio
    async def test_recall_finds_in_memory_file(self, registry, tmp_path):
        mem_file = tmp_path / "memory.md"
        mem_file.write_text("user prefers dark mode\nuser likes python\n")
        ctx = {"memory_path": str(mem_file)}
        result = await registry.execute("recall", {"query": "dark"}, ctx)
        assert "dark mode" in result

    @pytest.mark.asyncio
    async def test_recall_no_match(self, registry, tmp_path):
        mem_file = tmp_path / "memory.md"
        mem_file.write_text("user prefers dark mode\n")
        ctx = {"memory_path": str(mem_file)}
        result = await registry.execute("recall", {"query": "nonexistent"}, ctx)
        assert "not found" in result.lower() or "no matches" in result.lower()

    @pytest.mark.asyncio
    async def test_recall_missing_query(self, registry):
        result = await registry.execute("recall", {})
        assert "required" in result.lower() or "query" in result.lower()
