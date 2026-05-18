"""DagRunStore — CRUD for dag_runs table."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db.database import Database


class DagRunStore:
    def __init__(self, db: Database):
        self._db = db

    def save(self, run_id: str, data: dict) -> None:
        json_data = json.dumps(data, ensure_ascii=False)
        status = data.get("status", "running")
        session_id = data.get("session_id", "")
        self._db.execute_insert(
            "INSERT OR REPLACE INTO dag_runs (id, data, status, session_id, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (run_id, json_data, status, session_id),
        )

    def load(self, run_id: str) -> dict | None:
        rows = self._db.query(
            "SELECT data FROM dag_runs WHERE id = ?", (run_id,),
        )
        return json.loads(rows[0]["data"]) if rows else None

    def list_all(self) -> list[dict]:
        rows = self._db.query(
            "SELECT id, data FROM dag_runs ORDER BY created_at"
        )
        return [json.loads(r["data"]) for r in rows]

    def list_ids(self, status: str = "running") -> list[str]:
        rows = self._db.query(
            "SELECT id FROM dag_runs WHERE status = ? ORDER BY created_at",
            (status,),
        )
        return [r["id"] for r in rows]

    def get_pending_task(self) -> dict | None:
        rows = self._db.query(
            "SELECT id, data FROM dag_runs WHERE status = 'running' ORDER BY created_at"
        )
        for row in rows:
            data = json.loads(row["data"])
            for stage in data.get("stages", []):
                for task in stage.get("tasks", []):
                    if task.get("status") == "pending":
                        return {
                            "run_id": row["id"],
                            "data": data,
                            "task_id": task.get("id", "?"),
                            "prompt": task.get("prompt", "Execute this task"),
                            "session_id": data.get("session_id"),
                        }
        return None

    def delete(self, run_id: str) -> None:
        self._db.execute("DELETE FROM dag_runs WHERE id = ?", (run_id,))
        self._db.commit()
