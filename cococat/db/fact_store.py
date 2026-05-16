"""FactStore — insert and search facts with FTS5."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db.database import Database


class FactStore:
    def __init__(self, db: Database):
        self._db = db

    def insert(self, id: str, agent_id: str, fact: str, search_text: str,
               tags: str = "", session_id: str = "") -> int:
        return self._db.execute_insert(
            "INSERT INTO facts (id, agent_id, fact, search_text, tags, session_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (id, agent_id, fact, search_text, tags, session_id),
        )

    def rebuild_index(self) -> None:
        self._db.execute("INSERT INTO facts_fts(facts_fts) VALUES('rebuild')")
