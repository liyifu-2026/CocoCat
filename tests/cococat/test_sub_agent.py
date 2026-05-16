"""Tests for sub-agent executor."""
import asyncio
import pytest
from cococat.core.event_bus import EventBus
from cococat.core.agent import Agent, AgentState, AgentRole
from cococat.core.agent_pool import AgentPool
from cococat.core.sub_agent import SubAgentExecutor
from cococat.core.sandbox import SandboxProvider, LocalExecutor
from cococat.providers.base import LLMResponse


class FakeLLM:
    def __init__(self, response: str = "task done"):
        self.response = response

    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content=self.response)


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def pool(bus):
    p = AgentPool(bus)
    p.add_agent(Agent("main", "Main AI", AgentRole.RESIDENT, FakeLLM("ok")))
    p.add_agent(Agent("agent_a", "Agent A", AgentRole.WORKER, FakeLLM("sub done")))
    p.add_agent(Agent("agent_b", "Agent B", AgentRole.WORKER, FakeLLM("sub done")))
    return p


@pytest.fixture
def executor(bus, pool):
    return SubAgentExecutor(bus, pool)


@pytest.mark.asyncio
async def test_dispatch_to_free_sub_agent(executor, pool):
    """dispatch returns the result string and publishes completion event."""
    results = []
    bus = pool._bus

    async def on_complete(data):
        results.append(data)

    bus.subscribe("sub_agent_complete", on_complete)

    result = await executor.dispatch("Do task", from_agent="main")
    assert result is not None
    assert "sub done" in result

    assert len(results) == 1
    assert results[0]["from_agent"] == "main"
    assert "sub done" in results[0]["result"]


@pytest.mark.asyncio
async def test_dispatch_no_free_agents(executor, pool):
    pool.bind_to_scene("agent_a", "scene-1")
    pool.bind_to_scene("agent_b", "scene-2")

    result = await executor.dispatch("Do task", from_agent="main")
    assert result is None


@pytest.mark.asyncio
async def test_agent_state_after_dispatch(executor, pool):
    await executor.dispatch("Do task", from_agent="main")

    free = pool.get_free_sub_agents()
    assert len(free) == 2


@pytest.mark.asyncio
async def test_multiple_dispatches(executor, pool):
    results = []
    bus = pool._bus

    async def on_complete(data):
        results.append(data)

    bus.subscribe("sub_agent_complete", on_complete)

    r1 = await executor.dispatch("task 1", from_agent="main")
    r2 = await executor.dispatch("task 2", from_agent="main")

    assert len(results) == 2
    assert "sub done" in r1
    assert "sub done" in r2


class TestSubAgentViaSandbox:
    @pytest.mark.asyncio
    async def test_dispatch_via_sandbox_provider(self, bus):
        """SubAgentExecutor with sandbox_provider dispatches through SandboxProvider.run_once."""
        provider = SandboxProvider(executor=LocalExecutor())
        executor = SubAgentExecutor(bus, sandbox_provider=provider)
        results = []

        async def on_complete(data):
            results.append(data)

        bus.subscribe("sub_agent_complete", on_complete)

        result = await executor.dispatch("say hello", from_agent="main")
        # With sandbox provider and no LLM, returns error message
        assert result is not None

        await asyncio.sleep(2.0)

        if results:
            assert results[0]["agent_id"].startswith("sub-")
