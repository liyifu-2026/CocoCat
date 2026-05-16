"""Scheduler — simple asyncio-based recurring task runner."""

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger("cococat.scheduler")


class Scheduler:
    """Run callbacks at configurable intervals.

    Not a cron parser — just interval-based. For cron expressions, use the `cron` tool.
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self) -> None:
        """Start the scheduler loop."""
        self._running = True
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop all scheduled tasks."""
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
        self._tasks.clear()
        logger.info("Scheduler stopped")

    def add_interval(
        self,
        name: str,
        interval_seconds: float,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        """Add a recurring task that runs every interval_seconds."""
        if name in self._tasks:
            raise ValueError(f"Task '{name}' already exists")

        async def _loop():
            while self._running:
                await asyncio.sleep(interval_seconds)
                try:
                    await callback()
                except Exception:
                    logger.exception("Scheduler task '%s' failed", name)

        self._tasks[name] = asyncio.create_task(_loop())
        logger.info("Scheduler added task '%s' (every %.0fs)", name, interval_seconds)

    def remove(self, name: str) -> None:
        """Remove a scheduled task by name."""
        task = self._tasks.pop(name, None)
        if task:
            task.cancel()
            logger.info("Scheduler removed task '%s'", name)
