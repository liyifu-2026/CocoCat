"""Database — sqlite3 with WAL mode, compatible with existing cococat.db schema."""

from __future__ import annotations

import logging
import sqlite3
import uuid

logger = logging.getLogger("cococat.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA cache_size=-64000;

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    model TEXT NOT NULL,
    scene_id TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'stopped'
        CHECK (status IN ('stopped','running','error')),
    system_prompt TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_heartbeat_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_uuid TEXT UNIQUE NOT NULL,
    agent_id TEXT REFERENCES agents(id),
    user_id TEXT,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content TEXT NOT NULL,
    scene_id TEXT NOT NULL DEFAULT 'default',
    chat_group TEXT NOT NULL DEFAULT 'general',
    metadata TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','processing','replied','failed')),
    channel_type TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_scene_group
    ON messages(scene_id, chat_group, created_at);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_uuid TEXT UNIQUE NOT NULL,
    target_agent TEXT NOT NULL REFERENCES agents(id),
    source TEXT NOT NULL,
    method TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed','cancelled')),
    result TEXT,
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    task_type TEXT NOT NULL DEFAULT 'one_time',
    recurrence TEXT,
    parent_task_id INTEGER REFERENCES tasks(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_target
    ON tasks(status, target_agent)
    WHERE status IN ('pending','running');

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    roster TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    search_text TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    session_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    fact,
    search_text,
    tags,
    content='facts',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS dag_runs (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    session_id TEXT,
    created_by TEXT NOT NULL DEFAULT 'main',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL DEFAULT 'main',
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    """SQLite database wrapper with WAL mode.

    Compatible with the existing cococat.db schema from the Rust daemon.
    Adds `status` and `channel_type` to messages, and `facts` + `facts_fts` tables
    for long-term memory.
    """

    def __init__(self, path: str = "cococat.db"):
        self._path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def migrate(self) -> None:
        """Run schema migrations. Safe to call multiple times."""
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        # Safe migration: add columns if they don't exist
        for col, col_def in [
            ("status", "TEXT NOT NULL DEFAULT 'pending'"),
            ("channel_type", "TEXT"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE messages ADD COLUMN {col} {col_def}"
                )
            except sqlite3.OperationalError:
                pass  # column already exists

    def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Execute a query and return all rows as tuples."""
        cursor = self._conn.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        return [tuple(r) for r in rows]

    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """Execute a batch operation."""
        self._conn.executemany(sql, params_list)

    def execute_insert(self, sql: str, params: tuple = ()) -> int:
        """Execute an INSERT and return the last row id."""
        cursor = self._conn.execute(sql, params)
        row_id = cursor.lastrowid
        self._conn.commit()
        return row_id

    def commit(self) -> None:
        self._conn.commit()

    def save_dag(self, run_id: str, data: dict) -> None:
        """Save DAG run data. Replaces existing if same run_id."""
        import json
        json_data = json.dumps(data, ensure_ascii=False)
        status = data.get("status", "running")
        session_id = data.get("session_id", "")
        self._conn.execute(
            "INSERT OR REPLACE INTO dag_runs (id, data, status, session_id, updated_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (run_id, json_data, status, session_id),
        )
        self._conn.commit()

    def load_dag(self, run_id: str) -> dict | None:
        """Load DAG run data. Returns None if not found."""
        import json
        row = self._conn.execute(
            "SELECT data FROM dag_runs WHERE id = ?", (run_id,),
        ).fetchone()
        if row:
            return json.loads(row["data"])
        return None

    def list_dag_runs(self, status: str = "running") -> list[str]:
        """List run IDs with the given status."""
        rows = self._conn.execute(
            "SELECT id FROM dag_runs WHERE status = ? ORDER BY created_at",
            (status,),
        ).fetchall()
        return [r["id"] for r in rows]

    def get_pending_dag_task(self) -> dict | None:
        """Find one pending task across all runs. Returns task with run context. Used by TaskWorker."""
        import json
        rows = self._conn.execute(
            "SELECT id, data FROM dag_runs WHERE status = 'running' ORDER BY created_at"
        ).fetchall()
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

    def save_todos(self, todos: list, agent_id: str = "main") -> int:
        """Save todo items for an agent. Replaces existing todo data."""
        import json
        data = json.dumps(todos, ensure_ascii=False)
        # Upsert: delete old, insert new
        self._conn.execute("DELETE FROM todos WHERE agent_id = ?", (agent_id,))
        cursor = self._conn.execute(
            "INSERT INTO todos (agent_id, data) VALUES (?, ?)",
            (agent_id, data),
        )
        self._conn.commit()
        return cursor.lastrowid

    def load_todos(self, agent_id: str = "main") -> list:
        """Load todo items for an agent. Returns empty list if none found."""
        import json
        row = self._conn.execute(
            "SELECT data FROM todos WHERE agent_id = ? ORDER BY updated_at DESC LIMIT 1",
            (agent_id,),
        ).fetchone()
        if row:
            return json.loads(row["data"])
        return []

    # ── Agents ──────────────────────────────────────────────

    def list_agents(self) -> list[dict]:
        """List all agents."""
        rows = self._conn.execute(
            "SELECT id, name, role, status, scene_id, model, created_at FROM agents"
        ).fetchall()
        return [dict(r) for r in rows]

    def create_agent(self, id: str, name: str, role: str, model: str) -> None:
        """Create a new agent with status 'stopped'."""
        self._conn.execute(
            "INSERT INTO agents (id, name, role, model, status) VALUES (?, ?, ?, ?, 'stopped')",
            (id, name, role, model),
        )
        self._conn.commit()

    def get_agent(self, agent_id: str) -> dict | None:
        """Get a single agent by ID. Returns None if not found."""
        row = self._conn.execute(
            "SELECT id, name, role, status, scene_id, model FROM agents WHERE id = ?",
            (agent_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_agent_name(self, agent_id: str, name: str) -> None:
        """Update an agent's display name."""
        self._conn.execute("UPDATE agents SET name = ? WHERE id = ?", (name, agent_id))
        self._conn.commit()

    def update_agent_model(self, agent_id: str, model: str) -> None:
        """Update an agent's model and commit."""
        self._conn.execute("UPDATE agents SET model = ? WHERE id = ?", (model, agent_id))
        self._conn.commit()

    def list_running_agents(self) -> list[dict]:
        """List agents with status 'running' (id, name, role, model)."""
        rows = self._conn.execute(
            "SELECT id, name, role, model FROM agents WHERE status = 'running'"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_agent_model(self, agent_id: str) -> str | None:
        """Get the model string for an agent. Returns None if not found."""
        row = self._conn.execute(
            "SELECT model FROM agents WHERE id = ?", (agent_id,),
        ).fetchone()
        return row["model"] if row else None

    def seed_main_agent(self) -> bool:
        """Ensure the 'main' agent exists. Returns True if created."""
        existing = self._conn.execute(
            "SELECT id FROM agents WHERE id = 'main'"
        ).fetchone()
        if existing:
            return False
        self._conn.execute(
            "INSERT INTO agents (id, name, role, model, status) "
            "VALUES ('main', 'Coco', 'main', 'deepseek-chat', 'running')"
        )
        self._conn.commit()
        return True

    # ── Messages ────────────────────────────────────────────

    def save_message(self, msg_uuid: str, agent_id: str, user_id: str,
                     role: str, content: str, scene_id: str = "default",
                     channel_type: str | None = None) -> int:
        """Insert a message row. Returns lastrowid."""
        cursor = self._conn.execute(
            "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, channel_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_uuid, agent_id, user_id, role, content, scene_id, channel_type),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_chat_history(self, scene_id: str = "default", limit: int = 50) -> list[dict]:
        """Get chat history for a scene, newest last."""
        rows = self._conn.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE scene_id = ? AND chat_group = 'general' "
            "ORDER BY id DESC LIMIT ?",
            (scene_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ── Scenes ──────────────────────────────────────────────

    def list_scenes(self) -> list[dict]:
        """List all scenes from DB."""
        rows = self._conn.execute(
            "SELECT id, name, description, created_at FROM scenes"
        ).fetchall()
        return [dict(r) for r in rows]

    def create_scene(self, scene_id: str, name: str) -> None:
        """Create a new scene."""
        self._conn.execute(
            "INSERT INTO scenes (id, name) VALUES (?, ?)", (scene_id, name),
        )
        self._conn.commit()

    def get_scene(self, scene_id: str) -> dict | None:
        """Get a scene by ID from DB. Returns None if not found."""
        row = self._conn.execute(
            "SELECT id, name, description, roster FROM scenes WHERE id = ?",
            (scene_id,),
        ).fetchone()
        return dict(row) if row else None

    def delete_scene(self, scene_id: str) -> None:
        """Delete a scene by ID."""
        self._conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
        self._conn.commit()

    # ── Tasks ───────────────────────────────────────────────

    def create_task(self, task_uuid: str, target_agent: str, source: str,
                    method: str, params: str, status: str = "pending") -> int:
        """Insert a task row. Returns lastrowid."""
        cursor = self._conn.execute(
            "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (task_uuid, target_agent, source, method, params, status),
        )
        self._conn.commit()
        return cursor.lastrowid

    def claim_pending_kb_task(self) -> dict | None:
        """Claim one pending KB task (atomically). Returns task dict or None."""
        row = self._conn.execute(
            "SELECT task_uuid, target_agent, params FROM tasks "
            "WHERE source = 'kb' AND status = 'pending' "
            "ORDER BY created_at LIMIT 1"
        ).fetchone()
        if not row:
            return None
        task_uuid = row["task_uuid"]
        self._conn.execute(
            "UPDATE tasks SET status = 'running', started_at = datetime('now') "
            "WHERE task_uuid = ? AND status = 'pending'",
            (task_uuid,),
        )
        self._conn.commit()
        return dict(row)

    def complete_task(self, task_uuid: str, result: str) -> None:
        """Mark a task as completed with result."""
        self._conn.execute(
            "UPDATE tasks SET status = 'completed', result = ?, completed_at = datetime('now') "
            "WHERE task_uuid = ?",
            (result, task_uuid),
        )
        self._conn.commit()

    def fail_task(self, task_uuid: str, error: str) -> None:
        """Mark a task as failed with error message."""
        self._conn.execute(
            "UPDATE tasks SET status = 'failed', error = ? WHERE task_uuid = ?",
            (error, task_uuid),
        )
        self._conn.commit()

    # ── Lifecycle ───────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def new_uuid() -> str:
    return uuid.uuid4().hex[:16]
