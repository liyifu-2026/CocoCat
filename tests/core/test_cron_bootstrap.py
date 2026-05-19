import os, json
from unittest.mock import MagicMock
from cococat.core.bootstrap import _seed_cron_jobs


def _make_config_store():
    store = MagicMock()
    store.cron_dir = os.path.join("runs", "cron")
    return store


def test_seed_cron_jobs():
    entries = [
        {"name": "lint", "schedule": "@daily"},
        {"name": "dedup", "schedule": "@weekly"},
    ]
    config_store = _make_config_store()
    _seed_cron_jobs("test-agent", entries, config_store)
    for name in ("lint", "dedup"):
        path = os.path.join("runs", "cron", f"test-agent-{name}.json")
        assert os.path.exists(path), f"Expected {path} to exist"
        with open(path) as f:
            job = json.load(f)
        assert job["schedule"] in ("@daily", "@weekly")
        assert job["agent_id"] == "test-agent"
        os.remove(path)


def test_seed_cron_jobs_idempotent():
    entries = [{"name": "once", "schedule": "@daily"}]
    path = os.path.join("runs", "cron", "test-agent-once.json")
    config_store = _make_config_store()
    _seed_cron_jobs("test-agent", entries, config_store)
    assert os.path.exists(path)
    mtime1 = os.path.getmtime(path)
    _seed_cron_jobs("test-agent", entries, config_store)
    mtime2 = os.path.getmtime(path)
    assert mtime1 == mtime2, "File should not be overwritten"
    os.remove(path)
