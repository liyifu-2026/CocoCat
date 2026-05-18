"""SceneStore — CRUD for scenes table."""
from __future__ import annotations

import json
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

    def create_full(self, config: dict) -> str:
        """Create a scene with full configuration. Returns scene_id."""
        scene_id = config["id"]
        self._db.execute_insert(
            "INSERT INTO scenes (id, name, description, context, agent_id, status, "
            "purpose, kbs, skills, tools, channels, llm_config, visibility) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scene_id,
                config["name"],
                config.get("description", ""),
                config.get("context", ""),
                config.get("agent_id"),
                config.get("status", "running"),
                config.get("purpose", ""),
                json.dumps(config.get("kbs", [])),
                json.dumps(config.get("skills", [])),
                json.dumps(config.get("tools", [])),
                json.dumps(config.get("channels", [])),
                json.dumps(config.get("llm_config", {})),
                config.get("visibility", "private"),
            ),
        )
        return scene_id

    def update(self, scene_id: str, updates: dict) -> bool:
        """Update scene fields. `updates` keys match column names, values are SQL-ready strings."""
        setters = []
        values = []
        for key, val in updates.items():
            setters.append(f"{key} = ?")
            values.append(val)
        if not setters:
            return False
        setters.append("updated_at = datetime('now')")
        values.append(scene_id)
        self._db.execute(
            f"UPDATE scenes SET {', '.join(setters)} WHERE id = ?",
            tuple(values),
        )
        self._db.commit()
        return self._db._conn.total_changes > 0

    def set_status(self, scene_id: str, status: str) -> bool:
        """Transition scene to new status."""
        now = __import__('datetime').datetime.utcnow().isoformat()
        if status == "archived":
            self._db.execute(
                "UPDATE scenes SET status = ?, archived_at = ?, updated_at = ? WHERE id = ?",
                (status, now, now, scene_id),
            )
        else:
            self._db.execute(
                "UPDATE scenes SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, scene_id),
            )
        self._db.commit()
        return self._db._conn.total_changes > 0

    def get_full(self, scene_id: str) -> dict | None:
        """Get scene with all config fields hydrated."""
        import json
        row = self._db._conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for json_field in ("kbs", "skills", "tools", "channels", "llm_config"):
            try:
                d[json_field] = json.loads(d.get(json_field, "[]"))
            except (json.JSONDecodeError, TypeError):
                d[json_field] = [] if json_field != "llm_config" else {}
        return d
