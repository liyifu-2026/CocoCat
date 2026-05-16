"""TodoStore — save and load agent todo items."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db.database import Database


class TodoStore:
    def __init__(self, db: Database):
        self._db = db

    def save(self, todos: list, agent_id: str = "main") -> int:
        data = json.dumps(todos, ensure_ascii=False)
        self._db.execute("DELETE FROM todos WHERE agent_id = ?", (agent_id,))
        row_id = self._db.execute_insert(
            "INSERT INTO todos (agent_id, data) VALUES (?, ?)",
            (agent_id, data),
        )
        return row_id

    def load(self, agent_id: str = "main") -> list:
        rows = self._db.query(
            "SELECT data FROM todos WHERE agent_id = ? ORDER BY updated_at DESC LIMIT 1",
            (agent_id,),
        )
        if rows:
            return json.loads(rows[0]["data"])
        return []
