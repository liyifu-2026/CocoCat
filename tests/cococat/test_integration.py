"""Integration test — full chat flow with sub-agent delegation."""
import pytest
from cococat.core.event_bus import EventBus
from cococat.core.agent import Agent, AgentRole
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

    main = Agent("main", "Main AI", AgentRole.RESIDENT, FakeLLM("Dispatched to agent_a"))
    sub_a = Agent("agent_a", "Agent A", AgentRole.WORKER, FakeLLM("task completed"))
    sub_b = Agent("agent_b", "Agent B", AgentRole.WORKER, FakeLLM("task completed"))

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



