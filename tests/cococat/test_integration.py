"""Integration test — full chat flow with sub-agent delegation."""
import asyncio
import pytest
from cococat.core.event_bus import EventBus
from cococat.core.agent import Agent, AgentRole, AgentState
from cococat.core.agent_pool import AgentPool
from cococat.core.sub_agent import SubAgentExecutor
from cococat.providers.base import LLMResponse


class FakeLLM:
    def __init__(self, response: str = "ok"):
        self.response = response

    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content=self.response)


@pytest.mark.asyncio
async def test_full_chat_flow():
    """User → Main AI → sub agent → result published via EventBus."""
    bus = EventBus()
    pool = AgentPool(bus)

    main = Agent("main", "Main AI", AgentRole.MAIN, FakeLLM("Dispatched to agent_a"))
    sub_a = Agent("agent_a", "Agent A", AgentRole.SUB, FakeLLM("task completed"))
    sub_b = Agent("agent_b", "Agent B", AgentRole.SUB, FakeLLM("task completed"))

    pool.add_agent(main)
    pool.add_agent(sub_a)
    pool.add_agent(sub_b)

    executor = SubAgentExecutor(bus, pool)

    main_response = await main.run("帮我查退款流程")
    assert "agent_a" in main_response

    results = []
    async def collect(data):
        results.append(data)
    bus.subscribe("sub_agent_complete", collect)

    result = await executor.dispatch("查退款流程", from_agent="main")
    assert result is not None
    assert "task completed" in result

    assert len(results) == 1
    assert results[0]["result"] == "task completed"
    assert results[0]["from_agent"] == "main"


@pytest.mark.asyncio
async def test_scene_channel_flow():
    """External user → scene channel → bound sub AI → reply."""
    bus = EventBus()
    pool = AgentPool(bus)

    sub = Agent("agent_c", "Agent C", AgentRole.SUB, FakeLLM("退款流程：1.申请 2.审核 3.打款"))
    pool.add_agent(sub)
    pool.bind_to_scene("agent_c", "customer-service")

    agent = pool.get_agent("agent_c")
    assert agent.state == AgentState.WORKING
    assert agent.bound_scene == "customer-service"

    reply = await agent.run("我要退款")
    assert "退款" in reply
    assert agent.state == AgentState.WORKING


@pytest.mark.asyncio
async def test_scene_channel_queue():
    """Scene with bound agent processes messages sequentially."""
    bus = EventBus()
    pool = AgentPool(bus)

    order = []

    class OrderTrackingLLM:
        async def chat(self, messages, tools=None, **kwargs):
            content = messages[-1]["content"]
            order.append(content)
            await asyncio.sleep(0.05)
            return LLMResponse(content=f"Reply to: {content}")

    sub = Agent("agent_c", "Agent C", AgentRole.SUB, OrderTrackingLLM())
    pool.add_agent(sub)
    pool.bind_to_scene("agent_c", "customer-service")

    agent = pool.get_agent("agent_c")

    r1 = agent.run("msg1")
    r2 = agent.run("msg2")
    reply1, reply2 = await asyncio.gather(r1, r2)

    assert "msg1" in reply1
    assert "msg2" in reply2
    assert "msg1" in order
    assert "msg2" in order


@pytest.mark.asyncio
async def test_agent_pool_full():
    """When all sub agents are bound to scenes, dispatch returns None."""
    bus = EventBus()
    pool = AgentPool(bus, max_agents=2)

    sub1 = Agent("a", "A", AgentRole.SUB, FakeLLM())
    sub2 = Agent("b", "B", AgentRole.SUB, FakeLLM())
    pool.add_agent(sub1)
    pool.add_agent(sub2)

    # Bind both to scenes so no free agents remain
    pool.bind_to_scene("a", "scene-1")
    pool.bind_to_scene("b", "scene-2")

    executor = SubAgentExecutor(bus, pool)

    result = await executor.dispatch("task")
    assert result is None  # No free sub agents
