"""Tests for channel bridge."""
import asyncio
import pytest
from cococat.core.event_bus import EventBus
from cococat.core.agent import Agent, AgentRole
from cococat.core.agent_pool import AgentPool
from cococat.bridge import ChannelBridge


class FakeLLM:
    def __init__(self, response: str = "reply"):
        self.response = response

    async def chat(self, messages, tools=None, **kwargs):
        return {"content": self.response}


class FakeChannel:
    """Mock channel that records sent messages."""
    def __init__(self):
        self.sent: list[tuple] = []

    async def send_text(self, user_id: str, reply: str):
        self.sent.append((user_id, reply))


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def pool(bus):
    p = AgentPool(bus)
    p.add_agent(Agent("main", "Main AI", AgentRole.MAIN, FakeLLM("main reply")))
    p.add_agent(Agent("agent_c", "Agent C", AgentRole.SUB, FakeLLM("scene reply")))
    return p


@pytest.fixture
def bridge(bus, pool):
    return ChannelBridge(bus, pool)


@pytest.mark.asyncio
async def test_scene_handler_routes_to_bound_agent(bridge, pool):
    pool.bind_to_scene("agent_c", "customer-service")
    channel = FakeChannel()
    handler = bridge.make_scene_handler("customer-service", "wechat", channel)

    await handler("wx_user_123", "I want a refund")

    assert len(channel.sent) == 1
    assert channel.sent[0][1] == "scene reply"
    assert channel.sent[0][0] == "wx_user_123"


@pytest.mark.asyncio
async def test_scene_handler_no_bound_agent(bridge):
    channel = FakeChannel()
    handler = bridge.make_scene_handler("empty-scene", "wechat", channel)

    await handler("user", "hello")
    assert len(channel.sent) == 0  # No agent, no reply


@pytest.mark.asyncio
async def test_main_handler(bridge, pool):
    channel = FakeChannel()
    handler = bridge.make_main_handler("wechat", channel)

    await handler("wx_user", "help me")

    assert len(channel.sent) == 1
    assert channel.sent[0][1] == "main reply"


@pytest.mark.asyncio
async def test_bridge_publishes_events(bridge, bus, pool):
    pool.bind_to_scene("agent_c", "customer-service")
    channel = FakeChannel()

    events = []
    bus.subscribe("scene_message", lambda d: events.append(d))

    handler = bridge.make_scene_handler("customer-service", "wechat", channel)
    await handler("user_1", "message")
    await asyncio.sleep(0.05)

    assert len(events) == 1
    assert events[0]["scene_id"] == "customer-service"
    assert events[0]["user_id"] == "user_1"


@pytest.mark.asyncio
async def test_main_handler_no_main_agent(bus):
    """Main handler when main agent is not in pool — should silently return."""
    pool = AgentPool(bus)  # Empty pool
    bridge = ChannelBridge(bus, pool)
    channel = FakeChannel()
    handler = bridge.make_main_handler("feishu", channel)

    await handler("user", "hello")
    assert len(channel.sent) == 0  # No reply since no main agent


@pytest.mark.asyncio
async def test_scene_handler_agent_run_exception(bridge, pool):
    """If agent.run() raises, handler should not crash."""
    pool.bind_to_scene("agent_c", "customer-service")

    class FailingLLM:
        async def chat(self, messages, tools=None, **kwargs):
            raise RuntimeError("LLM down")

    pool.get_agent("agent_c")._llm = FailingLLM()

    channel = FakeChannel()
    handler = bridge.make_scene_handler("customer-service", "wechat", channel)

    await handler("user", "hello")  # Should not raise
    assert len(channel.sent) == 0  # No reply on error
