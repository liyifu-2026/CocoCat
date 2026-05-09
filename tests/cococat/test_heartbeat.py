"""Tests for heartbeat."""
import os
import tempfile
import asyncio
import pytest
from cococat.core.agent import Agent, AgentRole
from cococat.core.scheduler import Scheduler
from cococat.core.heartbeat import Heartbeat


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        content = messages[-1]["content"]
        return {"content": f"Heartbeat done: checked {content[:50]}"}


@pytest.mark.asyncio
async def test_heartbeat_runs_agent():
    with tempfile.TemporaryDirectory() as d:
        # Create heartbeat.md
        with open(os.path.join(d, "heartbeat.md"), "w") as f:
            f.write("- Check for new uploads\n- Review pending tasks")

        agent = Agent("main", "Main AI", AgentRole.MAIN, FakeLLM())
        scheduler = Scheduler()
        hb = Heartbeat(agent, scheduler, agent_dir=d, interval=0.05)

        results = []
        hb.on_complete = lambda msg: results.append(msg)

        await scheduler.start()
        hb.start()
        await asyncio.sleep(0.2)
        hb.stop()
        await scheduler.stop()

        assert len(results) >= 2  # Multiple heartbeat rounds
        assert "Heartbeat done" in results[0]


@pytest.mark.asyncio
async def test_heartbeat_default_when_no_file():
    with tempfile.TemporaryDirectory() as d:
        agent = Agent("main", "Main AI", AgentRole.MAIN, FakeLLM())
        scheduler = Scheduler()
        hb = Heartbeat(agent, scheduler, agent_dir=d, interval=0.05)

        results = []
        hb.on_complete = lambda msg: results.append(msg)

        await scheduler.start()
        hb.start()
        await asyncio.sleep(0.15)
        hb.stop()
        await scheduler.stop()

        assert len(results) >= 1


@pytest.mark.asyncio
async def test_heartbeat_stop():
    with tempfile.TemporaryDirectory() as d:
        agent = Agent("main", "Main AI", AgentRole.MAIN, FakeLLM())
        scheduler = Scheduler()
        hb = Heartbeat(agent, scheduler, agent_dir=d, interval=0.05)

        results = []
        hb.on_complete = lambda msg: results.append(msg)

        await scheduler.start()
        hb.start()
        await asyncio.sleep(0.1)
        hb.stop()

        before = len(results)
        await asyncio.sleep(0.1)
        assert len(results) == before  # No more after stop
        await scheduler.stop()
