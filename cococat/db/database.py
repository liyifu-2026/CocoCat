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

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_uuid TEXT UNIQUE NOT NULL,
    agent_id TEXT,
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

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    context TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','paused','archived','deleted')),
    purpose TEXT NOT NULL DEFAULT '',
    kbs TEXT NOT NULL DEFAULT '[]',
    skills TEXT NOT NULL DEFAULT '[]',
    tools TEXT NOT NULL DEFAULT '[]',
    channels TEXT NOT NULL DEFAULT '[]',
    llm_config TEXT NOT NULL DEFAULT '{}',
    visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private','shared')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channel_identities (
    user_id TEXT NOT NULL,
    channel_type TEXT NOT NULL,
    channel_user_id TEXT NOT NULL,
    PRIMARY KEY (channel_type, channel_user_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    source,
    content,
    agent_dir,
    tokenize='unicode61'
);
"""


class Database:
    """SQLite database wrapper with WAL mode.

    Provides connection management, migrations, and low-level query/execute.
    Entity-specific operations live in Store classes (SceneStore, MessageStore, etc.).
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
        self._migrate_scenes_table()
        from cococat.db.migrations import apply_migrations
        apply_migrations(self._conn)

    def _migrate_scenes_table(self) -> None:
        """Add new columns to scenes table if they don't exist (2026-05-18)."""
        new_columns = {
            "description": "TEXT NOT NULL DEFAULT ''",
            "context": "TEXT NOT NULL DEFAULT ''",
            "status": "TEXT NOT NULL DEFAULT 'running'",
            "purpose": "TEXT NOT NULL DEFAULT ''",
            "kbs": "TEXT NOT NULL DEFAULT '[]'",
            "skills": "TEXT NOT NULL DEFAULT '[]'",
            "tools": "TEXT NOT NULL DEFAULT '[]'",
            "channels": "TEXT NOT NULL DEFAULT '[]'",
            "llm_config": "TEXT NOT NULL DEFAULT '{}'",
            "visibility": "TEXT NOT NULL DEFAULT 'private'",
            "updated_at": "TEXT NOT NULL DEFAULT (datetime('now'))",
            "archived_at": "TEXT",
        }
        existing = {row[1] for row in self._conn.execute("PRAGMA table_info(scenes)")}
        for col_name, col_def in new_columns.items():
            if col_name not in existing:
                self._conn.execute(f"ALTER TABLE scenes ADD COLUMN {col_name} {col_def}")

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

    def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Run SELECT and return first row as dict, or None."""
        cursor = self._conn.execute(sql, params)
        row = cursor.fetchone()
        cursor.close()
        return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run SELECT and return all rows as dicts."""
        cursor = self._conn.execute(sql, params)
        rows = cursor.fetchall()
        cursor.close()
        return [dict(r) for r in rows]

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

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def new_uuid() -> str:
    return uuid.uuid4().hex[:16]
