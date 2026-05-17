import os, json
from cococat.core.bootstrap import _seed_cron_jobs


def test_seed_cron_jobs():
    entries = [
        {"name": "lint", "schedule": "@daily"},
        {"name": "dedup", "schedule": "@weekly"},
    ]
    _seed_cron_jobs("test-agent", entries)
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
    _seed_cron_jobs("test-agent", entries)
    assert os.path.exists(path)
    mtime1 = os.path.getmtime(path)
    _seed_cron_jobs("test-agent", entries)
    mtime2 = os.path.getmtime(path)
    assert mtime1 == mtime2, "File should not be overwritten"
    os.remove(path)
