"""Test task management tools: check_tasks, stop_task."""
import pytest
import json
import os

from cococat.core.tools import create_core_tools, ToolRegistry
from cococat.dag.store import FileDagStore


class TestCheckTasks:
    @pytest.mark.asyncio
    async def test_check_tasks_no_tasks(self, registry, tmp_path):
        store = FileDagStore(str(tmp_path / "runs"))
        tools = create_core_tools(dag_store=store)
        reg = ToolRegistry(tools)
        result = await reg.execute("check_tasks", {})
        assert "no tasks" in result.lower() or "pending" in result.lower()

    @pytest.mark.asyncio
    async def test_check_tasks_with_file(self, registry, tmp_path):
        store = FileDagStore(str(tmp_path / "runs"))
        tools = create_core_tools(dag_store=store)
        reg = ToolRegistry(tools)

        dag_yaml = """
stages:
  - id: s1
    tasks:
      - id: t1
        status: running
        description: test task
      - id: t2
        status: done
        description: done task
"""
        from cococat.core.tools.dag import _define_dag
        _define_dag(dag_yaml, {"dag_store": store})

        result = await reg.execute("check_tasks", {})
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
