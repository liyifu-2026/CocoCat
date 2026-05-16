"""Test Agent's base tools all have execute functions."""
import pytest

from cococat.core.agent import Agent, AgentRole


from cococat.providers.base import LLMResponse


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content="ok")


@pytest.fixture
def agent():
    return Agent(
        id="test-agent",
        name="Test Agent",
        role=AgentRole.SUB,
        llm=FakeLLM(),
        agent_dir=None,
    )


def test_agent_tools_have_execute(agent):
    tools = agent.get_tools()
    assert len(tools) > 0
    for t in tools:
        assert "execute" in t, f"Tool '{t.get('name')}' missing 'execute'"
        assert callable(t["execute"]), f"Tool '{t.get('name')}' execute is not callable"
