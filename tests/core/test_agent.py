"""Tests for cococat.core.agent."""
import os
import tempfile
import pytest
from cococat.core.agent import Agent, AgentRole
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
        role=AgentRole.RESIDENT,
        llm=fake_llm,
    )


@pytest.fixture
def sub_agent(fake_llm):
    return Agent(
        id="agent_a",
        name="Agent A",
        role=AgentRole.WORKER,
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
    assert main_agent.role == AgentRole.RESIDENT


@pytest.mark.asyncio
async def test_agent_run_returns_string(main_agent):
    response = await main_agent.run("Hello")
    assert isinstance(response, str)
    assert len(response) > 0


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
    agent = Agent(id="test", name="Test", role=AgentRole.WORKER, llm=fake_llm)

    result = await agent.run("Hello", session=session)
    assert len(result) > 0

    messages = await session.read()
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(user_msgs) >= 1
    assert user_msgs[-1]["content"] == "Hello"
    assert len(assistant_msgs) >= 1
