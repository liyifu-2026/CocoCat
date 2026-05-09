"""Tests for cococat.db."""
import sqlite3
import tempfile
import pytest
from cococat.db import Database


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    d = Database(path)
    d.migrate()
    yield d
    d.close()


def test_db_creates_tables(db):
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r[0] for r in tables}
    assert "agents" in names
    assert "messages" in names
    assert "tasks" in names
    assert "scenes" in names


def test_db_agent_crud(db):
    db.execute_insert(
        "INSERT INTO agents (id, name, role, model) VALUES (?, ?, ?, ?)",
        ("main", "Main AI", "main", "deepseek-chat"),
    )
    agents = db.execute("SELECT id, name, role FROM agents")
    assert ("main", "Main AI", "main") in agents


def test_db_message_insert_and_query(db):
    db.execute("INSERT INTO agents (id, name, role, model) VALUES ('main','M','main','gpt')")
    db.execute_insert(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("uuid-1", "main", "local", "user", "Hello", "default"),
    )
    db.execute_insert(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("uuid-2", "main", "local", "assistant", "Hi!", "default"),
    )
    msgs = db.execute(
        "SELECT role, content FROM messages WHERE scene_id = ? ORDER BY id", ("default",)
    )
    assert len(msgs) == 2
    assert msgs[0] == ("user", "Hello")
    assert msgs[1] == ("assistant", "Hi!")


def test_db_task_crud(db):
    db.execute("INSERT INTO agents (id, name, role, model) VALUES ('main','M','main','gpt')")
    db.execute_insert(
        "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("task-1", "main", "chat", "chat", "{}", "pending"),
    )
    tasks = db.execute("SELECT task_uuid, status FROM tasks WHERE status = 'pending'")
    assert ("task-1", "pending") in tasks

    db.execute("UPDATE tasks SET status = 'completed' WHERE task_uuid = ?", ("task-1",))
    db.commit()
    tasks = db.execute("SELECT task_uuid, status FROM tasks WHERE status = 'completed'")
    assert ("task-1", "completed") in tasks


def test_db_scene_crud(db):
    db.execute_insert(
        "INSERT INTO scenes (id, name) VALUES (?, ?)",
        ("customer-service", "Customer Service"),
    )
    scenes = db.execute("SELECT id, name FROM scenes")
    assert ("customer-service", "Customer Service") in scenes


def test_db_facts_table(db):
    """Facts table for long-term memory (FTS5)."""
    db.execute_insert(
        "INSERT INTO facts (id, agent_id, fact, search_text, tags, session_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("fact-1", "main", "User prefers short answers", "short answers preference",
         "preference,user", "session-1"),
    )
    # Rebuild FTS5 index after insert (content= table requires this)
    db.execute("INSERT INTO facts_fts(facts_fts) VALUES('rebuild')")
    results = db.execute(
        "SELECT fact FROM facts_fts WHERE facts_fts MATCH 'short'"
    )
    assert len(results) >= 1


def test_db_context_manager():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    with Database(path) as db:
        db.migrate()
        db.execute_insert(
            "INSERT INTO agents (id, name, role, model) VALUES ('x', 'X', 'sub', 'gpt')"
        )
    db2 = Database(path)
    agents = db2.execute("SELECT id FROM agents")
    assert ("x",) in agents
    db2.close()
