"""System cron tasks — memory compile chain + dream checkpoint polling."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("cococat.cron_tasks")


def bootstrap_system_cron_tasks(cron_dir: str) -> None:
    """Seed system cron entries into the cron directory. Idempotent."""
    os.makedirs(cron_dir, exist_ok=True)

    tasks = [
        {
            "id": "_compile_day",
            "type": "system",
            "task": "__compile_day__",
            "schedule": "0 2 * * *",
            "at_time": "02:00",
            "agent_id": "_system",
            "created_by": "_system",
            "status": "active",
            "last_run": 0,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": "_compile_week",
            "type": "system",
            "task": "__compile_week__",
            "schedule": "0 3 * * 0",
            "at_time": "03:00",
            "agent_id": "_system",
            "created_by": "_system",
            "status": "active",
            "last_run": 0,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": "_compile_longterm",
            "type": "system",
            "task": "__compile_longterm__",
            "schedule": "0 4 1 * *",
            "at_time": "04:00",
            "agent_id": "_system",
            "created_by": "_system",
            "status": "active",
            "last_run": 0,
            "created_at": datetime.now().isoformat(),
        },
        {
            "id": "_dream_poll",
            "type": "system",
            "task": "__dream_poll__",
            "schedule": "every 5 minutes",
            "agent_id": "_system",
            "created_by": "_system",
            "status": "active",
            "last_run": 0,
            "created_at": datetime.now().isoformat(),
        },
    ]

    for t in tasks:
        path = os.path.join(cron_dir, f"{t['id']}.json")
        if os.path.exists(path):
            continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(t, f, indent=2)
        logger.info("Seeded system cron: %s", t["id"])


def register_compile_handlers():
    """Register compile chain handlers that create per-user MemoryStore instances."""
    from cococat.core.cron_worker import register_system_task

    async def _compile_day():
        status = "ok"
        for user_dir in _list_user_agent_dirs():
            try:
                from cococat.memory.store import MemoryStore
                memory_dir = os.path.join(user_dir, "memory")
                store = MemoryStore(memory_dir=memory_dir)
                await store.compile_day()
            except Exception:
                logger.exception("compile_day failed for %s", user_dir)
                status = "partial_failure"
        return status

    async def _compile_week():
        status = "ok"
        for user_dir in _list_user_agent_dirs():
            try:
                from cococat.memory.store import MemoryStore
                memory_dir = os.path.join(user_dir, "memory")
                store = MemoryStore(memory_dir=memory_dir)
                await store.compile_week()
            except Exception:
                logger.exception("compile_week failed for %s", user_dir)
                status = "partial_failure"
        return status

    async def _compile_longterm():
        status = "ok"
        for user_dir in _list_user_agent_dirs():
            try:
                from cococat.memory.store import MemoryStore
                memory_dir = os.path.join(user_dir, "memory")
                store = MemoryStore(memory_dir=memory_dir)
                await store.compile_longterm()
            except Exception:
                logger.exception("compile_longterm failed for %s", user_dir)
                status = "partial_failure"
        return status

    async def _dream_poll():
        for user_dir in _list_user_agent_dirs():
            try:
                await _poll_dream_for_user(user_dir)
            except Exception:
                logger.exception("dream_poll failed for %s", user_dir)
        return "ok"

    register_system_task("__compile_day__", _compile_day)
    register_system_task("__compile_week__", _compile_week)
    register_system_task("__compile_longterm__", _compile_longterm)
    register_system_task("__dream_poll__", _dream_poll)
    logger.info("Registered system cron handlers: compile_day, compile_week, compile_longterm, dream_poll")


def _list_user_agent_dirs() -> list[str]:
    """List all user and scene agent directories under agents/."""
    agents_dir = "agents"
    if not os.path.isdir(agents_dir):
        return []
    result = []
    for name in os.listdir(agents_dir):
        if name.startswith("sub-") or name.startswith("_") or name == "empty":
            continue
        path = os.path.join(agents_dir, name)
        if os.path.isdir(path) and os.path.isdir(os.path.join(path, "memory")):
            result.append(path)

    # Also include scene directories
    scenes_dir = os.path.join(agents_dir, "scenes")
    if os.path.isdir(scenes_dir):
        for name in os.listdir(scenes_dir):
            path = os.path.join(scenes_dir, name)
            if os.path.isdir(path) and os.path.isdir(os.path.join(path, "memory")):
                result.append(path)

    return result


async def _poll_dream_for_user(user_dir: str) -> None:
    """Check user's session files for dream extraction."""
    sessions_dir = os.path.join(user_dir, "sessions")
    if not os.path.isdir(sessions_dir):
        return

    threshold = int(os.environ.get("COCOCAT_DREAM_TOKEN_THRESHOLD", "2000"))
    now = datetime.now().timestamp()

    for fname in sorted(os.listdir(sessions_dir)):
        if not fname.endswith(".jsonl"):
            continue
        session_path = os.path.join(sessions_dir, fname)
        mtime = os.path.getmtime(session_path)
        if (now - mtime) < 1800:  # modified within 30 min — still active
            continue

        ckpt_path = session_path.replace(".jsonl", ".dream_ckpt")
        last_line = 0
        if os.path.exists(ckpt_path):
            with open(ckpt_path) as f:
                last_line = int(f.read().strip() or 0)

        with open(session_path, encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) <= last_line:
            continue

        new_lines = lines[last_line:]
        new_tokens = sum(max(1, len(l) // 3) for l in new_lines)

        if new_tokens >= threshold:
            from cococat.memory.store import MemoryStore
            memory_dir = os.path.join(user_dir, "memory")
            store = MemoryStore(memory_dir=memory_dir)
            try:
                await store.dream(session_path)
            except Exception:
                logger.exception("dream failed for %s", session_path)

            with open(ckpt_path, "w") as f:
                f.write(str(len(lines)))
            logger.info("dream: extracted from %s (%d new tokens)", session_path, new_tokens)
