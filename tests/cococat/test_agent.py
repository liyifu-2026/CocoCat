"""Tests for cococat.core.agent."""
import os
import tempfile
import pytest
from cococat.core.agent import Agent, AgentState, AgentRole
from cococat.core.session import Session, SessionManager
from cococat.providers.base import LLMResponse


class FakeLLM:
    """Mock LLM that returns a fixed response."""
    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content="I'm the agent's response.")


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def main_agent(fake_llm):
    return Agent(
        id="main",
        name="Main AI",
        role=AgentRole.MAIN,
        llm=fake_llm,
    )


@pytest.fixture
def sub_agent(fake_llm):
    return Agent(
        id="agent_a",
        name="Agent A",
        role=AgentRole.SUB,
        llm=fake_llm,
    )


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def session_mgr():
    return SessionManager()


@pytest.mark.asyncio
async def test_agent_initial_state(main_agent):
    assert main_agent.id == "main"
    assert main_agent.role == AgentRole.MAIN
    assert main_agent.state == AgentState.IDLE
    assert main_agent.bound_scene is None


@pytest.mark.asyncio
async def test_agent_run_returns_string(main_agent):
    response = await main_agent.run("Hello")
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_agent_bind_to_scene(sub_agent):
    assert sub_agent.state == AgentState.IDLE
    sub_agent.bind_to_scene("customer-service")
    assert sub_agent.state == AgentState.WORKING
    assert sub_agent.bound_scene == "customer-service"


@pytest.mark.asyncio
async def test_agent_unbind_from_scene(sub_agent):
    sub_agent.bind_to_scene("customer-service")
    sub_agent.unbind()
    assert sub_agent.state == AgentState.IDLE
    assert sub_agent.bound_scene is None


@pytest.mark.asyncio
async def test_agent_bind_twice_overwrites(sub_agent):
    sub_agent.bind_to_scene("customer-service")
    sub_agent.bind_to_scene("development")
    assert sub_agent.bound_scene == "development"
    assert sub_agent.state == AgentState.WORKING


@pytest.mark.asyncio
async def test_main_ai_cannot_bind_to_scene(main_agent):
    with pytest.raises(ValueError, match="Main AI cannot bind to a scene"):
        main_agent.bind_to_scene("customer-service")


@pytest.mark.asyncio
async def test_sub_ai_bind_overwrites(sub_agent):
    sub_agent.bind_to_scene("customer-service")
    # Re-binding is allowed — overwrites existing scene
    sub_agent.bind_to_scene("development")
    assert sub_agent.bound_scene == "development"
    assert sub_agent.state == AgentState.WORKING


@pytest.mark.asyncio
async def test_agent_tools_in_idle_state(main_agent):
    tools = main_agent.get_tools()
    tool_names = [t["name"] for t in tools]
    # Idle agent has all core tools
    assert "read_file" in tool_names
    assert "bash" in tool_names
    assert "sub_agent" in tool_names


@pytest.mark.asyncio
async def test_sub_agent_tool_scoping(sub_agent):
    tools = sub_agent.get_tools()
    tool_names = [t["name"] for t in tools]
    assert "read_file" in tool_names

    sub_agent.bind_to_scene("customer-service")
    tools = sub_agent.get_tools()
    tool_names = [t["name"] for t in tools]
    # Still has core tools after binding
    assert "read_file" in tool_names
    assert "bash" in tool_names


@pytest.mark.asyncio
async def test_set_scene_tools_merged_with_base(sub_agent):
    scene_tools = [
        {"name": "crm_lookup", "description": "Lookup CRM data"},
        {"name": "refund", "description": "Process refund"},
    ]
    sub_agent.set_scene_tools(scene_tools)

    tools = sub_agent.get_tools()
    names = {t["name"] for t in tools}
    assert "read_file" in names     # core tool still present
    assert "bash" in names          # core tool still present
    assert "crm_lookup" in names    # scene tool added
    assert "refund" in names        # scene tool added


@pytest.mark.asyncio
async def test_set_scene_tools_cleared_on_unbind(sub_agent):
    sub_agent.set_scene_tools([{"name": "crm_lookup"}])
    sub_agent.unbind()

    tools = sub_agent.get_tools()
    names = {t["name"] for t in tools}
    assert "crm_lookup" not in names


@pytest.mark.asyncio
async def test_agent_run_saves_to_session(main_agent, tmp_dir, session_mgr):
    """Agent.run() with a Session should append user+assistant messages."""
    session = await session_mgr.create(tmp_dir)
    result = await main_agent.run("Hello", session=session)
    assert len(result) > 0

    messages = await session.read()
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "Hello"
    assert len(assistant_msgs) == 1


@pytest.mark.asyncio
async def test_agent_run_loads_history_from_session(main_agent, tmp_dir, session_mgr):
    """Agent.run() should use session.sanitized_read() for conversation history."""
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Previous question")
    await session.append("assistant", "Previous answer")

    result = await main_agent.run("Follow-up", session=session)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_agent_saves_to_session(tmp_dir, session_mgr, fake_llm):
    """Agent.run() with a Session should save messages to the session."""
    session = await session_mgr.create(tmp_dir)
    agent = Agent(id="test", name="Test", role=AgentRole.SUB, llm=fake_llm)

    result = await agent.run("Hello", session=session)
    assert len(result) > 0

    messages = await session.read()
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(user_msgs) >= 1
    assert user_msgs[-1]["content"] == "Hello"
    assert len(assistant_msgs) >= 1
