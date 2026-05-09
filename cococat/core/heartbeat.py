"""Heartbeat — periodic autonomous Main AI background check."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.core.agent import Agent
    from cococat.core.scheduler import Scheduler

logger = logging.getLogger("cococat.heartbeat")

DEFAULT_HEARTBEAT = """# Heartbeat Instructions
- Check if there are any unprocessed KB uploads that need ingestion.
- Review the system status and note anything that needs attention.
- If you discover new areas of focus or responsibilities, update this file.
"""


class Heartbeat:
    """Periodic Main AI autonomous background task.

    Every interval_seconds, the agent reads heartbeat.md, evaluates system state,
    and performs any needed actions. Results are logged to heartbeat.log.
    """

    def __init__(
        self,
        agent: Agent,
        scheduler: Scheduler,
        agent_dir: str = "agents/main",
        interval: float = 900,  # 15 minutes
    ):
        self._agent = agent
        self._scheduler = scheduler
        self._agent_dir = agent_dir
        self._interval = interval
        self._running = False
        self.on_complete: Optional[Callable[[str], None]] = None

    def start(self) -> None:
        """Start the heartbeat scheduler."""
        self._running = True
        self._scheduler.add_interval("heartbeat", self._interval, self._run)
        logger.info("Heartbeat started (every %.0fs)", self._interval)

    def stop(self) -> None:
        """Stop the heartbeat."""
        self._running = False
        self._scheduler.remove("heartbeat")
        logger.info("Heartbeat stopped")

    async def _run(self) -> None:
        """Execute one heartbeat cycle."""
        if not self._running:
            return

        # Read heartbeat instructions
        hb_path = os.path.join(self._agent_dir, "heartbeat.md")
        if os.path.exists(hb_path):
            with open(hb_path, encoding="utf-8") as f:
                instructions = f.read()
        else:
            instructions = DEFAULT_HEARTBEAT
            os.makedirs(self._agent_dir, exist_ok=True)
            with open(hb_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_HEARTBEAT)

        try:
            result = await self._agent.run(instructions)
            self._log(result)
            if self.on_complete:
                self.on_complete(result)
        except Exception:
            logger.exception("Heartbeat failed")

    def _log(self, result: str) -> None:
        """Append to heartbeat.log."""
        log_path = os.path.join(self._agent_dir, "heartbeat.log")
        os.makedirs(self._agent_dir, exist_ok=True)
        ts = datetime.now().isoformat()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {result[:500]}\n")
