"""TaskStore — CRUD for tasks table."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db.database import Database


class TaskStore:
    def __init__(self, db: Database):
        self._db = db

    def create(self, task_uuid: str, target_agent: str, source: str,
               method: str, params: str, status: str = "pending") -> int:
        row_id = self._db.execute_insert(
            "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task_uuid, target_agent, source, method, params, status),
        )
        return row_id

    def claim_pending_kb(self) -> dict | None:
        rows = self._db.query(
            "SELECT task_uuid, target_agent, params FROM tasks "
            "WHERE source = 'kb' AND status = 'pending' "
            "ORDER BY created_at LIMIT 1"
        )
        if not rows:
            return None
        task_uuid = rows[0]["task_uuid"]
        self._db.execute(
            "UPDATE tasks SET status = 'running', started_at = datetime('now') "
            "WHERE task_uuid = ? AND status = 'pending'",
            (task_uuid,),
        )
        self._db.commit()
        return rows[0]

    def complete(self, task_uuid: str, result: str) -> None:
        self._db.execute(
            "UPDATE tasks SET status = 'completed', result = ?, completed_at = datetime('now') "
            "WHERE task_uuid = ?",
            (result, task_uuid),
        )
        self._db.commit()

    def fail(self, task_uuid: str, error: str) -> None:
        self._db.execute(
            "UPDATE tasks SET status = 'failed', error = ? WHERE task_uuid = ?",
            (error, task_uuid),
        )
        self._db.commit()
