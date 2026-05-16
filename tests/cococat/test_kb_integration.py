"""Integration test — full KB ingest flow."""
import os
import tempfile
import asyncio
import pytest
from cococat.core.agent import Agent, AgentRole
from cococat.core.agent_pool import AgentPool
from cococat.core.event_bus import EventBus
from cococat.db import Database
from cococat.worker import TaskWorker
from cococat.providers.base import LLMResponse


class KBLLM:
    """LLM that returns realistic-looking FILE blocks for ingest."""
    async def chat(self, messages, tools=None, **kwargs):
        content = messages[-1]["content"]
        if "research analyst" in content.lower():
            return LLMResponse(content="Analysis: document describes CocoCat architecture.")
        return LLMResponse(content="""---FILE:wiki/concepts/test-concept.md---
---
type: concept
title: Test Concept
created: "2026-05-09"
summary: A test concept from integration test
tags: [test, integration]
---
# Test Concept

This is a test concept created by the ingest pipeline.

## See Also
- [[other-concept]]
---END FILE---
---FILE:wiki/entities/test-entity.md---
---
type: entity
title: Test Entity
created: "2026-05-09"
summary: A test entity
tags: [test]
---
# Test Entity

A test entity referenced by the concept.
---END FILE---""")


@pytest.mark.asyncio
async def test_full_kb_ingest_flow():
    import shutil
    with tempfile.TemporaryDirectory() as d:
        # Set up KB directory in working dir
        kb_dir = "knowledge/test-kb-int"
        raw_dir = os.path.join(kb_dir, "raw", "sources")
        os.makedirs(raw_dir, exist_ok=True)

        try:
            # Create source file
            with open(os.path.join(raw_dir, "test.md"), "w") as f:
                f.write("# CocoCat Architecture\nCocoCat is a multi-agent platform.")

            # Create DB with task
            db_path = os.path.join(d, "test.db")
            db = Database(db_path)
            db.migrate()
            db.execute_insert(
                "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, ?)",
                ("main", "Main AI", "main", "deepseek-chat", "running"),
            )
            db.execute_insert(
                "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("task-001", "main", "kb", "process_kb_source",
                 '{"kb_name": "test-kb-int", "filename": "test.md"}',
                 "pending"),
            )

            bus = EventBus()
            pool = AgentPool(bus)
            agent = Agent("main", "Main AI", AgentRole.MAIN, KBLLM())
            pool.add_agent(agent)

            worker = TaskWorker(db, pool, poll_interval=0.05)
            await worker.start()
            await asyncio.sleep(0.3)
            await worker.stop()

            tasks = db.execute("SELECT status, result FROM tasks WHERE task_uuid = 'task-001'")
            assert tasks[0][0] == "completed"
            assert "wiki pages" in tasks[0][1]

            entity = os.path.join(kb_dir, "wiki", "entities", "test-entity.md")
            concept = os.path.join(kb_dir, "wiki", "concepts", "test-concept.md")
            assert os.path.exists(entity)
            assert os.path.exists(concept)

            with open(entity) as f:
                assert "Test Entity" in f.read()

            index = os.path.join(kb_dir, "index.md")
            assert os.path.exists(index)
            with open(index) as f:
                assert "test-entity" in f.read()

            db.close()
        finally:
            shutil.rmtree(kb_dir, ignore_errors=True)
