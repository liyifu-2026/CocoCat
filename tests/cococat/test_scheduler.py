"""Tests for cococat.core.scheduler."""
import asyncio
import pytest
from cococat.core.scheduler import Scheduler


@pytest.mark.asyncio
async def test_scheduler_add_remove_task():
    s = Scheduler()
    await s.start()

    counter = 0

    async def inc():
        nonlocal counter
        counter += 1

    s.add_interval("test", 0.05, inc)
    await asyncio.sleep(0.15)
    assert counter >= 2  # Should have fired at least twice

    s.remove("test")
    await s.stop()


@pytest.mark.asyncio
async def test_scheduler_task_exception_does_not_crash():
    s = Scheduler()
    await s.start()

    ok_count = 0

    async def failing():
        raise RuntimeError("boom")

    async def ok():
        nonlocal ok_count
        ok_count += 1

    s.add_interval("failing", 0.05, failing)
    s.add_interval("ok", 0.05, ok)
    await asyncio.sleep(0.15)

    assert ok_count >= 2  # OK task should still run
    await s.stop()


@pytest.mark.asyncio
async def test_scheduler_duplicate_name_raises():
    s = Scheduler()
    await s.start()
    s.add_interval("test", 10, lambda: None)
    with pytest.raises(ValueError, match="already exists"):
        s.add_interval("test", 5, lambda: None)
    await s.stop()


@pytest.mark.asyncio
async def test_scheduler_stop_cancels_tasks():
    s = Scheduler()
    await s.start()

    tally = [0]

    async def inc():
        tally[0] += 1

    s.add_interval("test", 0.05, inc)
    await asyncio.sleep(0.15)
    await s.stop()

    before = tally[0]
    await asyncio.sleep(0.15)
    assert tally[0] == before


@pytest.mark.asyncio
async def test_scheduler_add_before_start_does_not_run():
    """Tasks added before start() should not fire (loop checks _running)."""
    s = Scheduler()
    counter = [0]

    async def inc():
        counter[0] += 1

    s.add_interval("early", 0.05, inc)
    # Don't start — task should not fire
    assert counter[0] == 0
    await s.stop()


@pytest.mark.asyncio
async def test_scheduler_remove_nonexistent():
    """Removing a nonexistent task should not raise."""
    s = Scheduler()
    s.remove("nonexistent")  # Should not raise
