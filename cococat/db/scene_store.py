"""SceneStore — CRUD for scenes table."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db.database import Database


class SceneStore:
    def __init__(self, db: Database):
        self._db = db

    def list_all(self) -> list[dict]:
        return self._db.query(
            "SELECT id, name, description, created_at FROM scenes"
        )

    def create(self, scene_id: str, name: str) -> None:
        self._db.execute_insert(
            "INSERT INTO scenes (id, name) VALUES (?, ?)", (scene_id, name),
        )

    def get(self, scene_id: str) -> dict | None:
        rows = self._db.query(
            "SELECT id, name, description, roster FROM scenes WHERE id = ?",
            (scene_id,),
        )
        return rows[0] if rows else None

    def delete(self, scene_id: str) -> None:
        self._db.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
        self._db.commit()
