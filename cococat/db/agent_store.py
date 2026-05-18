"""AgentStore — CRUD for agents table."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db.database import Database


class AgentStore:
    def __init__(self, db: Database):
        self._db = db

    def list_all(self) -> list[dict]:
        return self._db.query(
            "SELECT id, name, role, status, scene_id, model, created_at FROM agents"
        )

    def create(self, id: str, name: str, role: str, model: str) -> None:
        self._db.execute_insert(
            "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, 'stopped')",
            (id, name, role, model),
        )

    def get(self, agent_id: str) -> dict | None:
        rows = self._db.query(
            "SELECT id, name, role, status, scene_id, model FROM agents WHERE id = ?",
            (agent_id,),
        )
        return rows[0] if rows else None

    def create_full(self, config: dict) -> str:
        """Create an agent with full configuration including personality fields."""
        agent_id = config["id"]
        metadata = {
            "personality": config.get("personality", ""),
            "tone": config.get("tone", ""),
            "language": config.get("language", ""),
            "avatar": config.get("avatar", ""),
        }
        self._db.execute_insert(
            "INSERT INTO agents (id, name, role, model, scene_id, status, system_prompt, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agent_id,
                config["name"],
                config.get("role", "resident"),
                config.get("model", "deepseek-chat"),
                config.get("scene_id", "default"),
                config.get("status", "running"),
                config.get("system_prompt", ""),
                json.dumps(metadata),
            ),
        )
        return agent_id

    def get_personality(self, agent_id: str) -> dict:
        """Get agent personality fields from metadata."""
        row = self._db._conn.execute(
            "SELECT metadata FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if not row:
            return {}
        try:
            meta = json.loads(row["metadata"])
            return {
                "personality": meta.get("personality", ""),
                "tone": meta.get("tone", ""),
                "language": meta.get("language", ""),
                "avatar": meta.get("avatar", ""),
            }
        except (json.JSONDecodeError, TypeError):
            return {}

    def update_name(self, agent_id: str, name: str) -> None:
        self._db.execute("UPDATE agents SET name = ? WHERE id = ?", (name, agent_id))
        self._db.commit()

    def update_model(self, agent_id: str, model: str) -> None:
        self._db.execute("UPDATE agents SET model = ? WHERE id = ?", (model, agent_id))
        self._db.commit()

    def list_running(self) -> list[dict]:
        return self._db.query(
            "SELECT id, name, role, model FROM agents WHERE status = 'running'"
        )

    def get_model(self, agent_id: str) -> str | None:
        rows = self._db.query(
            "SELECT model FROM agents WHERE id = ?", (agent_id,),
        )
        return rows[0]["model"] if rows else None

    def seed_main(self) -> bool:
        existing = self._db.query("SELECT id FROM agents WHERE id = 'main'")
        if existing:
            return False
        self._db.execute_insert(
            "INSERT INTO agents (id, name, role, model, status) "
            "VALUES ('main', 'Coco', 'resident', 'deepseek-chat', 'running')"
        )
        return True
