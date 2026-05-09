"""Memory facts extraction — writes atomic facts to SQLite FTS5."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db import Database

logger = logging.getLogger("cococat.memory.facts")


class FactsExtractor:
    """Extracts atomic facts from session summaries into SQLite FTS5."""

    def __init__(self, llm: Any, db: Database, memory_dir: str = "memory"):
        self._llm = llm
        self._db = db
        self._memory_dir = memory_dir
        self._snapshots: dict[str, str] = {}  # session_id → last processed fingerprint

    async def process_dirty(self) -> int:
        """Process all sessions where summary fingerprint has changed. Returns count of new facts."""
        summaries_dir = os.path.join(self._memory_dir, "summaries")
        if not os.path.isdir(summaries_dir):
            return 0

        count = 0
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
            if self._snapshots.get(session_id) == fp:
                continue  # Already processed

            new_facts = await self._extract(data["summary"], session_id)
            if new_facts:
                for fact in new_facts:
                    self._db.execute_insert(
                        "INSERT INTO facts (id, agent_id, fact, search_text, tags, session_id) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (f"{session_id}-{fact['hash'][:8]}", "main",
                         fact["text"], fact["text"], fact.get("tags", ""),
                         session_id),
                    )
                self._db.execute("INSERT INTO facts_fts(facts_fts) VALUES('rebuild')")
                count += len(new_facts)

            self._snapshots[session_id] = fp

        return count

    async def _extract(self, summary: str, session_id: str) -> list[dict]:
        """Extract atomic facts from a session summary via LLM."""
        prompt = f"""Extract 1-3 key facts from this conversation summary.
Each fact should be a single sentence. Add a tag (preference/decision/context).

Summary: {summary[:1000]}

Return JSON array: [{{"text": "...", "tags": "..."}}]"""

        try:
            result = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
            )
            content = result.get("content", "") if isinstance(result, dict) else str(result)

            # Try to parse JSON from the response
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
