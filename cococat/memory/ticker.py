"""MemoryTicker — orchestrates session summarization and memory compilation."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.core.session import Session, SessionManager

logger = logging.getLogger("cococat.memory")

TURNS_PER_SUMMARY = 6


class MemoryTicker:
    """Orchestrates memory extraction from sessions."""

    def __init__(self, llm: Any, session_manager: SessionManager, memory_dir: str = "memory"):
        self._llm = llm
        self._session_mgr = session_manager
        self._memory_dir = memory_dir
        self._turn_counts: dict[str, int] = {}
        self._fingerprints: dict[str, str] = {}

    async def notify_turn(self, session: Session) -> None:
        sid = session.id
        self._turn_counts[sid] = self._turn_counts.get(sid, 0) + 1
        if self._turn_counts[sid] >= TURNS_PER_SUMMARY:
            await self._summarize(session)
            self._turn_counts[sid] = 0

    async def notify_session_end(self, session: Session) -> None:
        await self._summarize(session)
        self._turn_counts.pop(session.id, None)

    async def _summarize(self, session: Session) -> None:
        messages = await session.read()
        if len(messages) < 2:
            return

        content_hash = self._hash_messages(messages)
        fp = self._fingerprints.get(session.id)
        if fp == content_hash:
            return

        summary_dir = os.path.join(self._memory_dir, "summaries")
        os.makedirs(summary_dir, exist_ok=True)

        recent = messages[-20:]
        text = "\n".join(
            f"[{m['role']}]: {m.get('content', '')[:500]}"
            for m in recent
        )

        prompt = f"""Summarize this conversation segment in 2-3 sentences.
Focus on: key topics discussed, decisions made, user preferences revealed.

Conversation:
{text}

Summary:"""

        try:
            result = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
            )
            summary_text = result.content or ""
        except Exception:
            logger.exception("Summarization failed for session %s", session.id)
            return

        # Write summary
        summary_path = os.path.join(summary_dir, f"{session.id}.json")
        summary_data = {
            "session_id": session.id,
            "fingerprint": content_hash,
            "summary": summary_text[:1000],
            "message_count": len(messages),
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

        self._fingerprints[session.id] = content_hash
        logger.debug("Summary written for session %s", session.id)

    @staticmethod
    def _hash_messages(messages: list[dict]) -> str:
        """Fingerprint messages for cache invalidation."""
        text = json.dumps(
            [{"r": m["role"], "c": m.get("content", "")[:200]} for m in messages[-20:]],
            sort_keys=True,
        )
        return hashlib.sha256(text.encode()).hexdigest()[:16]
