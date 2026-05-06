"""SQLite database access layer — unified storage for py-agent modules."""
import os
import sqlite3
import threading

_DB_PATH = None
_local = threading.local()


def _find_db_path() -> str:
    env = os.environ.get("COCOCAT_DB")
    if env:
        return env
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "cococat.db"
    )


def set_db_path(path: str):
    global _DB_PATH
    _DB_PATH = path
    close_connection()


def get_db_path() -> str:
    if _DB_PATH is not None:
        return _DB_PATH
    return _find_db_path()


def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
    return _local.conn


def close_connection():
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def ensure_schema():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'worker',
            model TEXT NOT NULL DEFAULT 'gpt-4',
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
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_messages_scene_group
            ON messages(scene_id, chat_group, created_at);

        CREATE TABLE IF NOT EXISTS chat_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            announcement TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_group_members (
            group_id TEXT NOT NULL REFERENCES chat_groups(id),
            agent_id TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            PRIMARY KEY (group_id, agent_id)
        );
    """)
    conn.commit()
