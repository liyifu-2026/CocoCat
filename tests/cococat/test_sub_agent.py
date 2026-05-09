"""Tests for sub-agent executor."""
import asyncio
import pytest
from cococat.core.event_bus import EventBus
from cococat.core.agent import Agent, AgentState, AgentRole
from cococat.core.agent_pool import AgentPool
from cococat.core.sub_agent import SubAgentExecutor


class FakeLLM:
    def __init__(self, response: str = "task done"):
        self.response = response

    async def chat(self, messages, tools=None, **kwargs):
        return {"content": self.response}


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def pool(bus):
    p = AgentPool(bus)
    p.add_agent(Agent("main", "Main AI", AgentRole.MAIN, FakeLLM("ok")))
    p.add_agent(Agent("agent_a", "Agent A", AgentRole.SUB, FakeLLM("sub done")))
    p.add_agent(Agent("agent_b", "Agent B", AgentRole.SUB, FakeLLM("sub done")))
    return p


@pytest.fixture
def executor(bus, pool):
    return SubAgentExecutor(bus, pool)


@pytest.mark.asyncio
async def test_dispatch_to_free_sub_agent(executor, pool):
    results = []
    bus = pool._bus

    async def on_complete(data):
        results.append(data)

    bus.subscribe("sub_agent_complete", on_complete)

    task_id = await executor.dispatch("Do task", from_agent="main")
    assert task_id is not None

    # Wait for async completion
    await asyncio.sleep(0.1)

    assert len(results) == 1
    assert results[0]["task_id"] == task_id
    assert results[0]["from_agent"] == "main"


@pytest.mark.asyncio
async def test_dispatch_no_free_agents(executor, pool):
    # Bind all sub agents
    pool.bind_to_scene("agent_a", "scene-1")
    pool.bind_to_scene("agent_b", "scene-2")

    task_id = await executor.dispatch("Do task", from_agent="main")
    assert task_id is None  # No free agents


@pytest.mark.asyncio
async def test_agent_state_after_dispatch(executor, pool):
    task_id = await executor.dispatch("Do task", from_agent="main")
    await asyncio.sleep(0.1)

    # The sub agent that handled the task should be back to IDLE
    free = pool.get_free_sub_agents()
    assert len(free) == 2  # Both should be free again


@pytest.mark.asyncio
async def test_multiple_dispatches(executor, pool):
    results = []
    bus = pool._bus

    async def on_complete(data):
        results.append(data["task_id"])

    bus.subscribe("sub_agent_complete", on_complete)

    t1 = await executor.dispatch("task 1", from_agent="main")
    t2 = await executor.dispatch("task 2", from_agent="main")

    await asyncio.sleep(0.2)

    assert len(results) == 2
    assert t1 in results
    assert t2 in results
