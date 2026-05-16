"""Test simple tools: wait, current_status, todo_write."""
import pytest
import os
import json


class TestWait:
    @pytest.mark.asyncio
    async def test_wait_returns_ok(self, registry):
        result = await registry.execute("wait", {"seconds": 0.01})
        assert "slept" in result.lower() or "waited" in result.lower() or "ok" in result.lower()

    @pytest.mark.asyncio
    async def test_wait_missing_seconds(self, registry):
        result = await registry.execute("wait", {})
        assert "0s" in result or "0" in result

    @pytest.mark.asyncio
    async def test_wait_zero(self, registry):
        result = await registry.execute("wait", {"seconds": 0})
        assert "slept" in result.lower() or "waited" in result.lower() or "ok" in result.lower()


class TestCurrentStatus:
    @pytest.mark.asyncio
    async def test_current_status_returns_string(self, registry):
        result = await registry.execute("current_status", {})
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_current_status_with_context(self, registry):
        ctx = {"agent_id": "test-agent", "bound_scene": "test-scene"}
        result = await registry.execute("current_status", {}, ctx)
        assert "test-agent" in result or "test-scene" in result


class TestTodoWrite:
    @pytest.mark.asyncio
    async def test_todo_write_creates_file(self, registry, tmp_path):
        path = str(tmp_path / "todos.json")
        ctx = {"todos_path": path}
        todos = [{"task": "fix bug", "done": False}, {"task": "write tests", "done": True}]
        result = await registry.execute("todo_write", {"todos": todos}, ctx)
        assert "saved" in result.lower() or "written" in result.lower()
        assert os.path.exists(path)
        data = json.load(open(path))
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_todo_write_empty(self, registry, tmp_path):
        ctx = {"todos_path": str(tmp_path / "empty.json")}
        result = await registry.execute("todo_write", {"todos": []}, ctx)
        assert "saved" in result.lower() or "written" in result.lower()

    @pytest.mark.asyncio
    async def test_todo_write_invalid_todos(self, registry):
        result = await registry.execute("todo_write", {})
        assert "required" in result.lower() or "todos" in result.lower()


def test_todo_write_to_db():
    """_todo_write should use DB when db is in ctx."""
    from cococat.db.database import Database
    from cococat.core.tools.meta import _todo_write
    import tempfile, os

    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "test.db")
        db = Database(db_path)
        db.migrate()
        try:
            todos = [{"id": "1", "content": "Add tests", "status": "pending"}]
            ctx = {"db": db, "agent_id": "test-agent"}
            result = _todo_write(todos, ctx)
            assert "Saved" in result
            assert "DB" in result

            loaded = db.load_todos("test-agent")
            assert len(loaded) == 1
            assert loaded[0]["content"] == "Add tests"
        finally:
            db.close()

def test_todo_write_fallback_to_file():
    """_todo_write should fallback to file when no db in ctx."""
    from cococat.core.tools.meta import _todo_write
    import tempfile, os, json

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "todos.json")
        todos = [{"id": "1", "content": "Test", "status": "done"}]
        ctx = {"todos_path": path}
        result = _todo_write(todos, ctx)
        assert "Saved" in result
        assert "todos.json" in result

        with open(path) as f:
            loaded = json.load(f)
        assert len(loaded) == 1
        assert loaded[0]["content"] == "Test"
