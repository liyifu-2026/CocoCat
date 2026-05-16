"""Tests for task worker."""
import os
import tempfile
import asyncio
import pytest
from cococat.core.event_bus import EventBus
from cococat.core.agent import Agent, AgentRole
from cococat.core.agent_pool import AgentPool
from cococat.db import Database
from cococat.worker import TaskWorker
from cococat.providers.base import LLMResponse


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content="Ingested file successfully.")


@pytest.fixture
def db():
    db_path = "/tmp/test_worker.db"
    d = Database(db_path)
    d.migrate()
    yield d
    d.close()
    os.unlink(db_path)


@pytest.fixture
def pool():
    bus = EventBus()
    p = AgentPool(bus)
    p.add_agent(Agent("main", "Main AI", AgentRole.MAIN, FakeLLM()))
    return p


@pytest.mark.asyncio
async def test_worker_claims_and_processes_task(db, pool):
    db.execute_insert(
        "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, ?)",
        ("main", "Main AI", "main", "deepseek-chat", "running"),
    )
    db.execute_insert(
        "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("task-1", "main", "kb", "process_kb_source",
         '{"kb_name": "test-kb", "filename": "test.md"}',
         "pending"),
    )

    worker = TaskWorker(db, pool, poll_interval=0.05)
    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    tasks = db.execute("SELECT status, result FROM tasks WHERE task_uuid = 'task-1'")
    assert tasks[0][0] == "completed"
    assert "Ingested" in (tasks[0][1] or "")


@pytest.mark.asyncio
async def test_worker_no_pending_tasks(db, pool):
    """Worker handles empty task queue gracefully."""
    worker = TaskWorker(db, pool, poll_interval=0.05)
    await worker.start()
    await asyncio.sleep(0.15)
    await worker.stop()
    # Should not crash


@pytest.mark.asyncio
async def test_worker_agent_not_found(db, pool):
    """Task assigned to non-existent agent tests FK constraint."""
    # FK constraint prevents inserting tasks for missing agents.
    # This tests the DB-level integrity check.
    import sqlite3
    try:
        db.execute_insert(
            "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("task-2", "nonexistent", "kb", "process_kb_source", "{}", "pending"),
        )
        inserted = True
    except sqlite3.IntegrityError:
        inserted = False

    assert not inserted  # FK constraint should prevent insert


@pytest.mark.asyncio
async def test_worker_task_already_claimed(db, pool):
    """Worker skips tasks already marked as running."""
    db.execute_insert(
        "INSERT INTO agents (id, name, role, model, status) VALUES ('main','M','main','gpt','running')"
    )
    db.execute_insert(
        "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("task-3", "main", "kb", "process_kb_source", "{}", "running"),
    )

    worker = TaskWorker(db, pool, poll_interval=0.05)
    await worker.start()
    await asyncio.sleep(0.15)
    await worker.stop()

    tasks = db.execute("SELECT status FROM tasks WHERE task_uuid = 'task-3'")
    assert tasks[0][0] == "running"  # Unchanged
