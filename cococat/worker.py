"""Task worker — picks up pending KB tasks and processes them."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db import Database

logger = logging.getLogger("cococat.worker")


class TaskWorker:
    """Background worker that processes pending KB tasks."""

    def __init__(self, db: Database, poll_interval: float = 5.0):
        self._db = db
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._ws_manager = None

    def set_ws_manager(self, ws_manager):
        """Set WebSocket manager for notifications."""
        self._ws_manager = ws_manager

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
                await self._process_kb()
            except Exception:
                logger.exception("TaskWorker error")
            await asyncio.sleep(self._poll_interval)

    async def _process_kb(self) -> None:
        """Claim and process one pending KB task."""
        row = self._db.tasks.claim_pending_kb()
        if not row:
            return

        task_uuid = row["task_uuid"]
        target_agent = row["target_agent"]

        import json
        try:
            params = json.loads(row["params"])
        except json.JSONDecodeError:
            params = {}

        logger.warning("_process_kb: no agent pool available, failing task %s", task_uuid)
        self._db.tasks.fail(task_uuid, "Agent pool not available")
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
                summary = f"Ingested {filename} -> {len(ingest_result.written_files)} wiki pages"

            self._db.tasks.complete(task_uuid, summary)
        except Exception as e:
            self._db.tasks.fail(task_uuid, str(e)[:500])
