"""Test cron tool and worker."""
import json
import os
import time
import pytest
from cococat.core.cron_worker import CronWorker, _parse_schedule


class TestCron:
    @pytest.mark.asyncio
    async def test_cron_creates_entry(self, registry, tmp_path):
        ctx = {"cron_path": str(tmp_path)}
        result = await registry.execute("cron", {"schedule": "0 9 * * *", "task": "daily report"}, ctx)
        assert "scheduled" in result.lower() or "created" in result.lower()
        files = list(tmp_path.iterdir())
        assert len(files) > 0
        data = json.load(open(files[0]))
        assert data.get("schedule") == "0 9 * * *"
        assert "daily report" in str(data.get("task", data))

    @pytest.mark.asyncio
    async def test_cron_missing_schedule(self, registry):
        result = await registry.execute("cron", {"task": "test"})
        assert "required" in result.lower() or "schedule" in result.lower()

    @pytest.mark.asyncio
    async def test_cron_missing_task(self, registry):
        result = await registry.execute("cron", {"schedule": "0 9 * * *"})
        assert "required" in result.lower() or "task" in result.lower()


class TestParseSchedule:
    def test_hourly(self):
        assert _parse_schedule("hourly") == 3600

    def test_daily(self):
        assert _parse_schedule("daily") == 86400

    def test_weekly(self):
        assert _parse_schedule("weekly") == 604800

    def test_every_minutes(self):
        assert _parse_schedule("every 5 minutes") == 300
        assert _parse_schedule("every 10 minute") == 600

    def test_every_hours(self):
        assert _parse_schedule("every 2 hours") == 7200
        assert _parse_schedule("every 1 hour") == 3600

    def test_every_seconds(self):
        assert _parse_schedule("every 30 seconds") == 30

    def test_every_days(self):
        assert _parse_schedule("every 3 days") == 259200

    def test_cron_star_minute(self):
        assert _parse_schedule("*/15 * * * *") == 900

    def test_cron_star_hour(self):
        assert _parse_schedule("* */2 * * *") == 7200

    def test_unparseable(self):
        assert _parse_schedule("whenever the moon is full") is None

    def test_complex_cron_returns_none(self):
        assert _parse_schedule("30 9 1 * 1-5") is None


class TestCronWorker:
    @pytest.mark.asyncio
    async def test_creates_cron_dir_on_start(self, tmp_path):
        cron_dir = str(tmp_path / "cron_test")
        worker = CronWorker(pool=None, cron_dir=cron_dir)
        await worker.start()
        assert os.path.isdir(cron_dir)
        await worker.stop()

    @pytest.mark.asyncio
    async def test_processes_due_entry(self, tmp_path):
        cron_dir = str(tmp_path / "runs" / "cron")
        os.makedirs(cron_dir, exist_ok=True)

        dispatched = []

        class FakePool:
            def get_agent(self, name):
                class FakeAgent:
                    async def run(self, task):
                        dispatched.append(task)
                        return "ok"
                return FakeAgent()

        entry = {
            "id": "test001",
            "schedule": "every 1 seconds",
            "task": "hello world",
            "created_at": "2026-01-01T00:00:00",
            "status": "active",
            "last_run": 0,
        }
        filepath = os.path.join(cron_dir, "test001.json")
        with open(filepath, "w") as f:
            json.dump(entry, f)

        worker = CronWorker(pool=FakePool(), poll_interval=0.1, cron_dir=cron_dir)
        await worker.start()
        await __import__("asyncio").sleep(1.5)
        await worker.stop()

        assert len(dispatched) >= 1
        assert "hello world" in dispatched

        with open(filepath) as f:
            updated = json.load(f)
        assert updated.get("status") == "completed"
        assert updated.get("last_run") != 0

    @pytest.mark.asyncio
    async def test_skips_non_due_entry(self, tmp_path):
        cron_dir = str(tmp_path / "runs" / "cron")
        os.makedirs(cron_dir, exist_ok=True)

        dispatched = []

        class FakePool:
            def get_agent(self, _):
                class FakeAgent:
                    async def run(self, task):
                        dispatched.append(task)
                        return "ok"
                return FakeAgent()

        entry = {
            "id": "test002",
            "schedule": "every 1 hours",
            "task": "should not run",
            "created_at": "2026-01-01T00:00:00",
            "status": "active",
            "last_run": time.time(),
        }
        with open(os.path.join(cron_dir, "test002.json"), "w") as f:
            json.dump(entry, f)

        worker = CronWorker(pool=FakePool(), poll_interval=0.1, cron_dir=cron_dir)
        await worker.start()
        await __import__("asyncio").sleep(0.5)
        await worker.stop()

        assert len(dispatched) == 0

    @pytest.mark.asyncio
    async def test_skips_inactive_entry(self, tmp_path):
        cron_dir = str(tmp_path / "runs" / "cron")
        os.makedirs(cron_dir, exist_ok=True)

        dispatched = []

        class FakePool:
            def get_agent(self, _):
                class FakeAgent:
                    async def run(self, task):
                        dispatched.append(task)
                        return "ok"
                return FakeAgent()

        entry = {
            "id": "inactive001",
            "schedule": "every 1 seconds",
            "task": "inactive job",
            "created_at": "2026-01-01T00:00:00",
            "status": "paused",
            "last_run": 0,
        }
        with open(os.path.join(cron_dir, "inactive001.json"), "w") as f:
            json.dump(entry, f)

        worker = CronWorker(pool=FakePool(), poll_interval=0.1, cron_dir=cron_dir)
        await worker.start()
        await __import__("asyncio").sleep(1.0)
        await worker.stop()
        assert len(dispatched) == 0
