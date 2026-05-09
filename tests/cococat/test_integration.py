"""Integration test — full chat flow with sub-agent delegation."""
import asyncio
import pytest
from cococat.core.event_bus import EventBus
from cococat.core.agent import Agent, AgentRole, AgentState
from cococat.core.agent_pool import AgentPool
from cococat.core.sub_agent import SubAgentExecutor


class FakeLLM:
    def __init__(self, response: str = "ok"):
        self.response = response

    async def chat(self, messages, tools=None, **kwargs):
        return {"content": self.response}


@pytest.mark.asyncio
async def test_full_chat_flow():
    """User → Main AI → sub agent → result."""
    bus = EventBus()
    pool = AgentPool(bus)

    main = Agent("main", "Main AI", AgentRole.MAIN, FakeLLM("Dispatched to agent_a"))
    sub_a = Agent("agent_a", "Agent A", AgentRole.SUB, FakeLLM("task completed"))
    sub_b = Agent("agent_b", "Agent B", AgentRole.SUB, FakeLLM("task completed"))

    pool.add_agent(main)
    pool.add_agent(sub_a)
    pool.add_agent(sub_b)

    executor = SubAgentExecutor(bus, pool)

    # User sends message to Main AI
    user_msg = "帮我查退款流程"
    main_response = await main.run(user_msg)
    assert "agent_a" in main_response  # Main AI decided to delegate

    # Main AI dispatches to a free sub agent
    results = []
    async def collect(data):
        results.append(data)
    bus.subscribe("sub_agent_complete", collect)

    task_id = await executor.dispatch("查退款流程", from_agent="main")
    assert task_id is not None

    # Wait for completion
    await asyncio.sleep(0.1)
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

    # External user message arrives via channel
    channel_msg = "我要退款"
    reply = await agent.run(channel_msg)
    assert "退款" in reply

    # Agent remains bound after processing
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
            return {"content": f"Reply to: {content}"}

    sub = Agent("agent_c", "Agent C", AgentRole.SUB, OrderTrackingLLM())
    pool.add_agent(sub)
    pool.bind_to_scene("agent_c", "customer-service")

    agent = pool.get_agent("agent_c")

    # Two messages arrive nearly simultaneously
    r1 = agent.run("msg1")
    r2 = agent.run("msg2")

    reply1, reply2 = await asyncio.gather(r1, r2)

    assert "msg1" in reply1
    assert "msg2" in reply2
    # Both messages should be processed (order may vary since they're concurrent)
    assert "msg1" in order
    assert "msg2" in order


@pytest.mark.asyncio
async def test_agent_pool_full():
    """When all sub agents are busy, dispatch returns None."""
    bus = EventBus()
    pool = AgentPool(bus, max_agents=2)

    sub1 = Agent("a", "A", AgentRole.SUB, FakeLLM())
    sub2 = Agent("b", "B", AgentRole.SUB, FakeLLM())
    pool.add_agent(sub1)
    pool.add_agent(sub2)

    executor = SubAgentExecutor(bus, pool)

    # Dispatch to both
    t1 = await executor.dispatch("task 1")
    t2 = await executor.dispatch("task 2")
    assert t1 is not None
    assert t2 is not None

    # Third dispatch should fail — all busy
    t3 = await executor.dispatch("task 3")
    assert t3 is None
