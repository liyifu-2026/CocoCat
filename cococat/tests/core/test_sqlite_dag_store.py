"""Tests for SqliteDagStore."""
import pytest
from cococat.db import Database
from cococat.core.dag_store import SqliteDagStore


@pytest.fixture
def store():
    """Create a SqliteDagStore backed by an in-memory SQLite database."""
    db = Database(":memory:")
    db.migrate()
    return SqliteDagStore(db)


class TestSqliteDagStore:
    def test_save_and_load(self, store):
        data = {"run_id": "r1", "status": "running", "stages": []}
        store.save("r1", data)

        loaded = store.load("r1")
        assert loaded is not None
        assert loaded["run_id"] == "r1"
        assert loaded["status"] == "running"

    def test_load_missing_returns_none(self, store):
        assert store.load("nonexistent") is None

    def test_save_overwrites(self, store):
        store.save("r1", {"run_id": "r1", "status": "running"})
        store.save("r1", {"run_id": "r1", "status": "done"})

        loaded = store.load("r1")
        assert loaded["status"] == "done"

    def test_get_pending_task_finds_first(self, store):
        store.save("r1", {
            "run_id": "r1", "status": "running",
            "stages": [{"id": "s1", "tasks": [
                {"id": "t1", "status": "done"},
                {"id": "t2", "status": "pending", "prompt": "do it"},
            ]}],
        })

        pending = store.get_pending_task()
        assert pending is not None
        assert pending["run_id"] == "r1"
        assert pending["task_id"] == "t2"
        assert pending["prompt"] == "do it"

    def test_get_pending_task_returns_none_when_all_done(self, store):
        store.save("r1", {
            "run_id": "r1", "status": "running",
            "stages": [{"id": "s1", "tasks": [
                {"id": "t1", "status": "done"},
            ]}],
        })

        assert store.get_pending_task() is None

    def test_get_pending_task_returns_none_when_empty(self, store):
        assert store.get_pending_task() is None

    def test_list_all(self, store):
        store.save("r1", {"run_id": "r1", "status": "running"})
        store.save("r2", {"run_id": "r2", "status": "done"})

        all_runs = store.list_all()
        assert len(all_runs) == 2
        run_ids = {r["run_id"] for r in all_runs}
        assert run_ids == {"r1", "r2"}

    def test_list_all_empty(self, store):
        assert store.list_all() == []
