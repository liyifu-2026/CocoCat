"""Tests for memory tools — pin/unpin/list_pins on pinned.md."""
import os
import tempfile
import pytest
from cococat.core.tools.memory_tools import _pin, _unpin, _list_pins
from cococat.core.types import ToolContext, MemoryEnv


def _make_ctx(agent_dir):
    return ToolContext(
        agent_id="test-agent",
        agent_dir=agent_dir,
        memory=MemoryEnv(agent_dir=agent_dir),
    )


class TestPinToPinnedMd:
    def test_pin_writes_to_pinned_md(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _make_ctx(d)
            result = _pin("User prefers short answers", ctx)
            assert "Pinned" in result

            pinned_path = os.path.join(d, "pinned.md")
            assert os.path.exists(pinned_path)
            with open(pinned_path) as f:
                content = f.read()
            assert "User prefers short answers" in content

    def test_pin_does_not_write_to_memory_md(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _make_ctx(d)
            _pin("Test fact", ctx)

            memory_md = os.path.join(d, "memory", "memory.md")
            assert not os.path.exists(memory_md), "pin should NOT write to memory/memory.md"

    def test_list_pins_returns_all_pinned_facts(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _make_ctx(d)
            _pin("Fact A", ctx)
            _pin("Fact B", ctx)

            result = _list_pins(ctx)
            assert "Fact A" in result
            assert "Fact B" in result

    def test_list_pins_empty(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _make_ctx(d)
            result = _list_pins(ctx)
            assert "No pinned facts" in result or "empty" in result.lower()

    def test_unpin_removes_from_pinned_md(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _make_ctx(d)
            _pin("Important note", ctx)
            _pin("Temporary note", ctx)

            result = _unpin("Temporary", ctx)
            assert "Unpinned" in result

            pinned_path = os.path.join(d, "pinned.md")
            with open(pinned_path) as f:
                content = f.read()
            assert "Important note" in content
            assert "Temporary note" not in content

    def test_pin_requires_fact(self):
        ctx = _make_ctx("/tmp/test")
        result = _pin("", ctx)
        assert "required" in result.lower() or "Error" in result


class TestRememberForget:
    def _make_ctx(self, d):
        from cococat.core.types import ToolContext, MemoryEnv
        return ToolContext(
            agent_id="test-agent",
            agent_dir=d,
            memory=MemoryEnv(agent_dir=d),
        )

    def test_remember_writes_to_memory_md(self):
        import tempfile
        from cococat.core.tools.memory_tools import _remember
        with tempfile.TemporaryDirectory() as d:
            ctx = self._make_ctx(d)
            result = _remember("Meeting at 3pm tomorrow", ctx)
            assert "Meeting at 3pm tomorrow" in result or "Pinned" in result or "Noted" in result

            mem_path = os.path.join(d, "memory", "memory.md")
            assert os.path.exists(mem_path)
            with open(mem_path) as f:
                content = f.read()
            assert "Meeting at 3pm tomorrow" in content

    def test_forget_removes_from_memory_md(self):
        import tempfile
        from cococat.core.tools.memory_tools import _remember, _forget
        with tempfile.TemporaryDirectory() as d:
            ctx = self._make_ctx(d)
            _remember("Important - keep this", ctx)
            _remember("Trash - delete this", ctx)

            result = _forget("Trash", ctx)
            assert "Unpinned" in result or "Forgotten" in result or "Removed" in result

            mem_path = os.path.join(d, "memory", "memory.md")
            with open(mem_path) as f:
                content = f.read()
            assert "Important" in content
            assert "Trash" not in content
