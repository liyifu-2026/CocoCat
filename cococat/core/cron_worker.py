"""Cron worker — background process that reads and executes scheduled cron jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING, Callable

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
    if schedule.startswith("@"):
        schedule = schedule[1:]

    # "every N minutes" style
    for pat, multiplier in _INTERVAL_PATTERNS:
        m = pat.match(schedule)
        if m:
            return float(m.group(1)) * multiplier

    if schedule in _NAMED:
        return float(_NAMED[schedule])

    # "every N minutes" without @
    for pat, multiplier in _INTERVAL_PATTERNS:
        m = pat.match(schedule)
        if m:
            return float(m.group(1)) * multiplier

    fields = schedule.split()
    if len(fields) == 5:
        return _parse_cron_fields(fields)

    return None


# ── System task routing ───────────────────────────────────────

_SYSTEM_TASK_HANDLERS: dict[str, Callable] = {}

def register_system_task(name: str, handler: Callable) -> None:
    _SYSTEM_TASK_HANDLERS[name] = handler


async def _dispatch_system_task(name: str) -> str:
    handler = _SYSTEM_TASK_HANDLERS.get(name)
    if not handler:
        return f"Unknown system task: {name}"
    return await handler()


def _is_time_match(at_time: str, tolerance: float = 30.0) -> bool:
    """Check if current wall-clock time matches at_time (HH:MM) within tolerance seconds."""
    if not at_time:
        return True
    try:
        parts = at_time.strip().split(":")
        expected_h = int(parts[0])
        expected_m = int(parts[1])
    except (ValueError, IndexError):
        return True
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute + now.second / 60.0
    expected_minutes = expected_h * 60 + expected_m
    diff = abs(now_minutes - expected_minutes) * 60
    return diff <= tolerance


def _to_timestamp(value) -> float:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return 0
    if isinstance(value, (int, float)):
        return float(value)
    return 0


async def _dispatch(task: str, target_agent_id: str, pool, sub_executor) -> None:
    if target_agent_id and pool:
        agent = pool.get_agent(target_agent_id)
        if agent:
            await agent.run(task)
            return
        if sub_executor:
            result = await sub_executor.dispatch(task, from_agent="cron")
            if not result:
                raise RuntimeError(f"Sub-agent dispatch returned no result for task")
            return
        raise RuntimeError(f"Agent '{target_agent_id}' not found and no sub_executor available")

    if sub_executor:
        result = await sub_executor.dispatch(task, from_agent="cron")
        if not result:
            raise RuntimeError("Sub-agent dispatch returned no result for task")
        return

    main = pool.get_agent("main") if pool else None
    if main:
        await main.run(task)
        return
    raise RuntimeError("No dispatch target available")


def _parse_cron_fields(fields: list[str]) -> float | None:
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
    """Background worker that polls the cron directory and dispatches due tasks."""

    def __init__(
        self,
        pool: AgentPool,
        sub_executor: SubAgentExecutor | None = None,
        poll_interval: float = POLL_INTERVAL,
        cron_dir: str = CRON_DIR,
    ):
        self._pool = pool
        self._sub_executor = sub_executor
        self._poll_interval = poll_interval
        self._cron_dir = cron_dir
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        os.makedirs(self._cron_dir, exist_ok=True)
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
        if not os.path.isdir(self._cron_dir):
            return

        now = time.time()
        entries = [f for f in os.listdir(self._cron_dir) if f.endswith(".json")]
        for filename in entries:
            filepath = os.path.join(self._cron_dir, filename)
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

        last_run = _to_timestamp(entry.get("last_run", 0))
        if (now - last_run) < interval:
            return

        at_time = entry.get("at_time", "")
        if at_time and interval >= 86400 and not _is_time_match(at_time):
            return

        entry["last_run"] = datetime.now().isoformat()
        entry["status"] = "running"
        with open(filepath, "w") as f:
            json.dump(entry, f, indent=2)

        task = entry.get("task", "")
        task_id = entry.get("id", "unknown")
        target_agent_id = entry.get("agent_id", "")
        is_system = entry.get("type") == "system" or task.startswith("__")

        logger.info("CronWorker dispatching %s -> %s: %s", task_id, target_agent_id or "pool", task)

        try:
            if is_system and task.startswith("__"):
                entry["status"] = await _dispatch_system_task(task)
            else:
                await _dispatch(task, target_agent_id, self._pool, self._sub_executor)
                entry["status"] = "completed"
        except Exception as e:
            logger.exception("CronWorker task %s failed", task_id)
            entry["status"] = "failed"
            entry["error"] = str(e)[:500]

        entry["last_run"] = datetime.now().isoformat()
        with open(filepath, "w") as f:
            json.dump(entry, f, indent=2)
