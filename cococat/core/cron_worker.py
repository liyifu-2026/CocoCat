"""Cron worker — background process that reads and executes scheduled cron jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.core.agent_pool import AgentPool
    from cococat.core.sub_agent import SubAgentExecutor

logger = logging.getLogger("cococat.cron_worker")

CRON_DIR = "runs/cron"
POLL_INTERVAL = 60  # seconds between directory scans

_INTERVAL_PATTERNS = [
    (re.compile(r"every\s+(\d+)\s+seconds?"), 1),
    (re.compile(r"every\s+(\d+)\s+minutes?"), 60),
    (re.compile(r"every\s+(\d+)\s+hours?"), 3600),
    (re.compile(r"every\s+(\d+)\s+days?"), 86400),
]

_NAMED = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
}


def _parse_schedule(schedule: str) -> float | None:
    """Parse a schedule string into interval seconds. Returns None if unparseable."""
    schedule = schedule.strip().lower()

    if schedule in _NAMED:
        return float(_NAMED[schedule])

    for pat, multiplier in _INTERVAL_PATTERNS:
        m = pat.match(schedule)
        if m:
            return float(m.group(1)) * multiplier

    fields = schedule.split()
    if len(fields) == 5:
        return _parse_cron_fields(fields)

    return None


def _parse_cron_fields(fields: list[str]) -> float | None:
    """Parse 5-field cron expression to seconds. Returns None if not simple enough."""
    minute = fields[0]
    hour = fields[1]
    dom = fields[2]
    month = fields[3]
    dow = fields[4]

    all_star = all(f in ("*", "?") for f in [dom, month, dow])

    if not all_star:
        return None

    if minute.startswith("*/"):
        try:
            return float(minute[2:]) * 60
        except ValueError:
            pass

    if hour.startswith("*/"):
        try:
            return float(hour[2:]) * 3600
        except ValueError:
            pass

    if minute.isdigit() and hour == "*":
        return 3600
    if hour.isdigit() and minute.isdigit():
        return 86400

    return None


class CronWorker:
    """Background worker that polls runs/cron/ and dispatches due tasks."""

    def __init__(
        self,
        pool: AgentPool,
        sub_executor: SubAgentExecutor | None = None,
        poll_interval: float = POLL_INTERVAL,
    ):
        self._pool = pool
        self._sub_executor = sub_executor
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        os.makedirs(CRON_DIR, exist_ok=True)
        self._task = asyncio.create_task(self._loop())
        logger.info("CronWorker started (poll every %.0fs)", self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("CronWorker stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._process_cron_dir()
            except Exception:
                logger.exception("CronWorker error")
            await asyncio.sleep(self._poll_interval)

    async def _process_cron_dir(self) -> None:
        if not os.path.isdir(CRON_DIR):
            return

        now = time.time()
        entries = [f for f in os.listdir(CRON_DIR) if f.endswith(".json")]
        for filename in entries:
            filepath = os.path.join(CRON_DIR, filename)
            try:
                await self._process_entry(filepath, now)
            except Exception:
                logger.exception("CronWorker failed processing %s", filename)

    async def _process_entry(self, filepath: str, now: float) -> None:
        try:
            with open(filepath, "r") as f:
                entry = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return

        if entry.get("status") != "active":
            return

        interval = _parse_schedule(entry.get("schedule", ""))
        if interval is None:
            return

        last_run = entry.get("last_run", 0)
        if isinstance(last_run, str):
            try:
                last_run = datetime.fromisoformat(last_run).timestamp()
            except ValueError:
                last_run = 0

        if (now - last_run) < interval:
            return

        entry["last_run"] = datetime.now().isoformat()
        entry["status"] = "running"
        with open(filepath, "w") as f:
            json.dump(entry, f, indent=2)

        task = entry.get("task", "")
        task_id = entry.get("id", "unknown")
        logger.info("CronWorker dispatching %s: %s", task_id, task)

        try:
            if self._sub_executor:
                result = await self._sub_executor.dispatch(task, from_agent="cron")
                if result:
                    logger.info("CronWorker task %s dispatched → %s", task_id, result)
            else:
                main = self._pool.get_agent("main")
                if main:
                    await main.run(task)

            entry["status"] = "completed"
        except Exception as e:
            logger.exception("CronWorker task %s failed", task_id)
            entry["status"] = "failed"
            entry["error"] = str(e)[:500]

        entry["last_run"] = datetime.now().isoformat()
        with open(filepath, "w") as f:
            json.dump(entry, f, indent=2)
