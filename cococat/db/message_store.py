"""MessageStore — insert and query messages table."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db.database import Database


class MessageStore:
    def __init__(self, db: Database):
        self._db = db

    def save(self, msg_uuid: str, agent_id: str, user_id: str,
             role: str, content: str, scene_id: str = "default",
             channel_type: str | None = None) -> int:
        return self._db.execute_insert(
            "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, channel_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_uuid, agent_id, user_id, role, content, scene_id, channel_type),
        )

    def get_chat_history(self, scene_id: str = "default", limit: int = 50) -> list[dict]:
        rows = self._db.query(
            "SELECT role, content, created_at FROM messages "
            "WHERE scene_id = ? AND chat_group = 'general' "
            "ORDER BY id DESC LIMIT ?",
            (scene_id, limit),
        )
        return [dict(r) for r in reversed(rows)]
