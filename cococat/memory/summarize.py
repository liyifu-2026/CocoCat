"""On-the-fly session summarization (Ticker)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Callable

logger = logging.getLogger("cococat.memory")

TURNS_PER_SUMMARY = 6


class SummarizeMemory:
    """On-the-fly session summarization with fingerprint caching.

    Owns its own state (_turn_counts, _fingerprints) — no shared mutable dicts.
    """

    def __init__(self, memory_dir: str = "memory", get_llm: Callable[[], Any] | None = None):
        self._memory_dir = memory_dir
        self._get_llm = get_llm or (lambda: None)
        self._turn_counts: dict[str, int] = {}
        self._fingerprints: dict[str, str] = {}

    async def notify_turn(self, session: Any) -> None:
        sid = session.id
        self._turn_counts[sid] = self._turn_counts.get(sid, 0) + 1
        if self._turn_counts[sid] >= TURNS_PER_SUMMARY:
            await self._summarize(session)
            self._turn_counts[sid] = 0

    async def notify_session_end(self, session: Any) -> None:
        await self._summarize(session)
        self._turn_counts.pop(session.id, None)

    async def _summarize(self, session: Any) -> None:
        messages = await session.read()
        if len(messages) < 2:
            return

        content_hash = self._hash_messages(messages)
        if self._fingerprints.get(session.id) == content_hash:
            return

        summary_dir = os.path.join(self._memory_dir, "summaries")
        os.makedirs(summary_dir, exist_ok=True)

        recent = messages[-20:]
        text = "\n".join(
            f"[{m['role']}]: {m.get('content', '')[:500]}"
            for m in recent
        )

        prompt = (
            "Summarize this conversation segment in 2-3 sentences.\n"
            "Focus on: key topics discussed, decisions made, user preferences revealed.\n\n"
            f"Conversation:\n{text}\n\nSummary:"
        )

        llm = self._get_llm()
        if not llm:
            return

        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            summary_text = result.content or ""
        except Exception:
            logger.exception("Summarization failed for session %s", session.id)
            return

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

    @staticmethod
    def _hash_messages(messages: list[dict]) -> str:
        text = json.dumps(
            [{"r": m["role"], "c": m.get("content", "")[:200]} for m in messages[-20:]],
            sort_keys=True,
        )
        return hashlib.sha256(text.encode()).hexdigest()[:16]
