"""Auto-Dream — thin wrapper delegating to MemoryStore."""

from __future__ import annotations

import logging

logger = logging.getLogger("cococat.dream")


async def try_auto_dream(agent, session_path: str) -> None:
    """Fire-and-forget: extract facts from session history via MemoryStore."""
    from cococat.memory.store import MemoryStore
    store = MemoryStore()
    try:
        await store.dream(session_path)
    except Exception:
        logger.warning("auto_dream failed, retry next session", exc_info=True)
