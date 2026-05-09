"""Task worker — picks up pending KB tasks and processes them via agent."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db import Database
    from cococat.core.agent_pool import AgentPool

logger = logging.getLogger("cococat.worker")


class TaskWorker:
    """Background worker that processes pending KB ingest tasks.

    Polls the tasks table for pending KB tasks, claims them,
    and hands them to the main agent for processing.
    """

    def __init__(self, db: Database, pool: AgentPool, poll_interval: float = 5.0):
        self._db = db
        self._pool = pool
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("TaskWorker started (poll every %.0fs)", self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("TaskWorker stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._process_pending()
            except Exception:
                logger.exception("TaskWorker error")
            await asyncio.sleep(self._poll_interval)

    async def _process_pending(self) -> None:
        """Claim and process one pending KB task."""
        rows = self._db.execute(
            "SELECT task_uuid, target_agent, params FROM tasks "
            "WHERE source = 'kb' AND status = 'pending' "
            "ORDER BY created_at LIMIT 1"
        )
        if not rows:
            return

        task_uuid, target_agent, params_json = rows[0]

        # Claim the task
        self._db.execute(
            "UPDATE tasks SET status = 'running', started_at = datetime('now') "
            "WHERE task_uuid = ? AND status = 'pending'",
            (task_uuid,),
        )
        self._db.commit()

        import json
        try:
            params = json.loads(params_json)
        except json.JSONDecodeError:
            params = {}

        agent = self._pool.get_agent(target_agent)
        if not agent:
            self._db.execute(
                "UPDATE tasks SET status = 'failed', error = ? WHERE task_uuid = ?",
                (f"Agent '{target_agent}' not found", task_uuid),
            )
            self._db.commit()
            return

        kb_name = params.get("kb_name", "unknown")
        filename = params.get("filename", "unknown")

        logger.info("Processing KB task %s: %s/%s", task_uuid, kb_name, filename)

        try:
            from cococat.ingest.ingest import IngestPipeline
            kb_dir = f"knowledge/{kb_name}"
            pipeline = IngestPipeline(agent._llm, kb_dir)
            ingest_result = await pipeline.ingest(filename, kb_name=kb_name)

            if ingest_result.skipped:
                summary = f"Skipped (cache hit): {filename}"
            else:
                summary = f"Ingested {filename} → {len(ingest_result.written_files)} wiki pages"

            self._db.execute(
                "UPDATE tasks SET status = 'completed', result = ?, completed_at = datetime('now') "
                "WHERE task_uuid = ?",
                (summary, task_uuid),
            )
        except Exception as e:
            self._db.execute(
                "UPDATE tasks SET status = 'failed', error = ? WHERE task_uuid = ?",
                (str(e)[:500], task_uuid),
            )

        self._db.commit()
