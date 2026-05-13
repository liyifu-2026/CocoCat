"""Test task management tools: check_tasks, stop_task."""
import pytest
import json
import os


class TestCheckTasks:
    @pytest.mark.asyncio
    async def test_check_tasks_no_tasks(self, registry, tmp_path):
        ctx = {"tasks_path": str(tmp_path)}
        result = await registry.execute("check_tasks", {}, ctx)
        assert "no tasks" in result.lower() or "pending" in result.lower() or "0" in result

    @pytest.mark.asyncio
    async def test_check_tasks_with_file(self, registry, tmp_path):
        tasks = [
            {"id": "t1", "status": "running", "description": "test task"},
            {"id": "t2", "status": "done", "description": "done task"},
        ]
        path = str(tmp_path / "tasks.json")
        json.dump(tasks, open(path, "w"))
        ctx = {"tasks_path": str(tmp_path)}
        result = await registry.execute("check_tasks", {}, ctx)
        assert "t1" in result
        assert "running" in result.lower()


class TestStopTask:
    @pytest.mark.asyncio
    async def test_stop_task_missing_id(self, registry):
        result = await registry.execute("stop_task", {})
        assert "required" in result.lower() or "task_id" in result.lower()

    @pytest.mark.asyncio
    async def test_stop_task_creates_cancel_marker(self, registry, tmp_path):
        cancel_dir = str(tmp_path / "cancellations")
        ctx = {"cancel_dir": cancel_dir}
        result = await registry.execute("stop_task", {"task_id": "task-123"}, ctx)
        assert "cancelled" in result.lower() or "stopped" in result.lower() or "cancel" in result.lower()
        marker = os.path.join(cancel_dir, "task-123.cancel")
        assert os.path.exists(marker)
