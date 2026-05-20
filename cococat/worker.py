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
        pass
