"""FTS5 atomic fact extraction and indexing."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

logger = logging.getLogger("cococat.memory")


class FactsMemory:
    """FTS5 atomic fact extraction from session summaries.

    Owns its own state (_fact_snapshots) — no shared mutable dicts.
    """

    def __init__(self, memory_dir: str = "memory", db: Any = None, get_llm: Callable[[], Any] | None = None):
        self._memory_dir = memory_dir
        self._db = db
        self._get_llm = get_llm or (lambda: None)
        self._fact_snapshots: dict[str, str] = {}

    async def extract_facts(self) -> int:
        summaries_dir = os.path.join(self._memory_dir, "summaries")
        if not os.path.isdir(summaries_dir):
            return 0

        count = 0
        fact_store = self._db.facts if self._db else None
        for fname in os.listdir(summaries_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(summaries_dir, fname)
            session_id = fname[:-5]
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            fp = data.get("fingerprint", "")
            if self._fact_snapshots.get(session_id) == fp:
                continue

            new_facts = await self._extract_atomic(data["summary"], session_id)
            if new_facts and fact_store:
                for fact in new_facts:
                    fact_store.insert(
                        f"{session_id}-{fact['hash'][:8]}", "main",
                        fact["text"], fact["text"], fact.get("tags", ""),
                        session_id,
                    )
                fact_store.rebuild_index()
                count += len(new_facts)

            self._fact_snapshots[session_id] = fp

        return count

    async def _extract_atomic(self, summary: str, session_id: str) -> list[dict]:
        prompt = (
            "Extract 1-3 key facts from this conversation summary.\n"
            "Each fact should be a single sentence. Add a tag (preference/decision/context).\n\n"
            f"Summary: {summary[:1000]}\n\n"
            'Return JSON array: [{"text": "...", "tags": "..."}]'
        )
        llm = self._get_llm()
        if not llm:
            return []
        try:
            result = await llm.chat(messages=[{"role": "user", "content": prompt}])
            content = result.content or ""
            json_start = content.find("[")
            json_end = content.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                facts = json.loads(content[json_start:json_end])
                return [
                    {"text": f["text"], "tags": f.get("tags", ""),
                     "hash": str(hash(f["text"]))}
                    for f in facts if isinstance(f, dict) and "text" in f
                ]
        except Exception:
            logger.exception("Facts extraction failed for %s", session_id)
        return []
