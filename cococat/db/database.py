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

    Provides connection management, migrations, and low-level query/execute.
    Entity-specific operations live in Store classes (AgentStore, TaskStore, etc.).
    """

    def __init__(self, path: str = "cococat.db"):
        self._path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def migrate(self) -> None:
        """Run schema migrations. Safe to call multiple times."""
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        for col, col_def in [
            ("status", "TEXT NOT NULL DEFAULT 'pending'"),
            ("channel_type", "TEXT"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE messages ADD COLUMN {col} {col_def}"
                )
            except sqlite3.OperationalError:
                pass

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run a SELECT query and return rows as dicts."""
        cursor = self._conn.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        return [dict(r) for r in rows]

    def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Run a query and return all rows as tuples (legacy, use query() for dicts)."""
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

    @property
    def agents(self):
        if not hasattr(self, "_agents"):
            from cococat.db.agent_store import AgentStore
            self._agents = AgentStore(self)
        return self._agents

    @property
    def tasks(self):
        if not hasattr(self, "_tasks"):
            from cococat.db.task_store import TaskStore
            self._tasks = TaskStore(self)
        return self._tasks

    @property
    def scenes(self):
        if not hasattr(self, "_scenes"):
            from cococat.db.scene_store import SceneStore
            self._scenes = SceneStore(self)
        return self._scenes

    @property
    def messages(self):
        if not hasattr(self, "_messages"):
            from cococat.db.message_store import MessageStore
            self._messages = MessageStore(self)
        return self._messages

    @property
    def facts(self):
        if not hasattr(self, "_facts"):
            from cococat.db.fact_store import FactStore
            self._facts = FactStore(self)
        return self._facts

    @property
    def todos(self):
        if not hasattr(self, "_todos"):
            from cococat.db.todo_store import TodoStore
            self._todos = TodoStore(self)
        return self._todos

    @property
    def dag_runs(self):
        if not hasattr(self, "_dag_runs"):
            from cococat.db.dag_run_store import DagRunStore
            self._dag_runs = DagRunStore(self)
        return self._dag_runs

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def new_uuid() -> str:
    return uuid.uuid4().hex[:16]
