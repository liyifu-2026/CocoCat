"""Tests for cococat.core.agent_pool."""
import pytest
from cococat.core.event_bus import EventBus
from cococat.core.agent import Agent, AgentRole
from cococat.providers.base import LLMResponse


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content="response")


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def pool(bus):
    from cococat.core.agent_pool import AgentPool
    p = AgentPool(bus, max_agents=5)
    p.add_agent(Agent("main", "Main AI", AgentRole.RESIDENT, FakeLLM()))
    p.add_agent(Agent("agent_a", "Agent A", AgentRole.WORKER, FakeLLM()))
    p.add_agent(Agent("agent_b", "Agent B", AgentRole.WORKER, FakeLLM()))
    return p


@pytest.mark.asyncio
async def test_pool_list_agents(pool):
    agents = pool.list_agents()
    assert len(agents) == 3
    ids = {a.id for a in agents}
    assert ids == {"main", "agent_a", "agent_b"}


@pytest.mark.asyncio
async def test_pool_get_free_sub_agents(pool):
    free = pool.get_free_sub_agents()
    assert len(free) == 2  # agent_a, agent_b (main excluded)


@pytest.mark.asyncio
async def test_pool_max_agents():
    from cococat.core.agent_pool import AgentPool
    bus = EventBus()
    p = AgentPool(bus, max_agents=2)
    p.add_agent(Agent("a", "A", AgentRole.WORKER, FakeLLM()))
    p.add_agent(Agent("b", "B", AgentRole.WORKER, FakeLLM()))
    assert not p.add_agent(Agent("c", "C", AgentRole.WORKER, FakeLLM()))


@pytest.mark.asyncio
async def test_get_agent_nonexistent(pool):
    agent = pool.get_agent("nonexistent")
    assert agent is None


@pytest.mark.asyncio
async def test_add_agent_overwrites_existing(pool):
    """Adding an agent with same ID replaces the old one."""
    bus = pool._bus
    old = Agent("agent_a", "Old Name", AgentRole.WORKER, FakeLLM())
    new = Agent("agent_a", "New Name", AgentRole.WORKER, FakeLLM())
    pool.add_agent(old)
    pool.add_agent(new)
    agent = pool.get_agent("agent_a")
    assert agent.name == "New Name"
