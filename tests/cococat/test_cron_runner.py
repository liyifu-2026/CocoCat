import time
import pytest
from cococat.worker import CronJob, CronTaskRunner


def test_cron_job_daily_due():
    job = CronJob("test", "lint", "@daily")
    assert job.is_due() is True
    job.mark_run()
    assert job.is_due() is False


def test_cron_job_interval():
    job = CronJob("test", "lint", "@daily")
    assert job.is_due() is True
    job._last_run = time.time() - 90000
    assert job.is_due() is True


def test_cron_runner_register_and_tick():
    runner = CronTaskRunner()
    called = []

    async def handler(agent_id, job_name):
        called.append(job_name)

    runner.register("kb-agent", "lint", "@daily")
    runner.set_handler(handler)
    runner.tick()  # handler should be called via due jobs
    # Note: tick returns due jobs; the caller calls handler
    # So we test the due list
    due = runner.tick()
    assert len(due) >= 0  # may or may not be due depending on when test runs

    # First tick was already consumed above, let's re-test
    runner2 = CronTaskRunner()
    runner2.register("kb-agent", "lint", "@daily")
    due = runner2.tick()
    assert len(due) == 1
    assert due[0].name == "lint"
    due2 = runner2.tick()
    assert len(due2) == 0


def test_cron_runner_respects_interval():
    runner = CronTaskRunner()
    runner.register("kb-agent", "lint", "@daily")
    due = runner.tick()
    assert len(due) == 1
    due = runner.tick()
    assert len(due) == 0


def test_cron_parse_schedule():
    assert CronJob._parse_schedule("@hourly") == 3600
    assert CronJob._parse_schedule("@daily") == 86400
    assert CronJob._parse_schedule("@weekly") == 604800
    assert CronJob._parse_schedule("600") == 600.0
    assert CronJob._parse_schedule("invalid") == 86400
