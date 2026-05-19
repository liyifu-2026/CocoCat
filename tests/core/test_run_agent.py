"""Tests for run_agent pure function."""
import tempfile
import pytest
from cococat.core.agent import AgentConfig, run_agent
from cococat.providers.base import LLMResponse


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content="Hello from Agent!")


@pytest.mark.asyncio
async def test_run_agent_returns_string():
    with tempfile.TemporaryDirectory() as d:
        config = AgentConfig(id="test", name="Test", role="worker",
                             system_prompt="You are a helpful assistant.",
                             tools=[], agent_dir=d)
        result = await run_agent(config, FakeLLM(), "Hi")
        assert isinstance(result, str)
        assert "Hello from Agent" in result


@pytest.mark.asyncio
async def test_run_agent_saves_to_session():
    from cococat.core.session import SessionManager
    with tempfile.TemporaryDirectory() as d:
        config = AgentConfig(id="test", name="Test", role="worker",
                             system_prompt="You are a helpful assistant.",
                             tools=[], agent_dir=d)
        mgr = SessionManager()
        session = await mgr.create(d)
        await run_agent(config, FakeLLM(), "Hello", session=session)
        messages = await session.read()
        user_msgs = [m for m in messages if m["role"] == "user"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(user_msgs) >= 1
        assert len(assistant_msgs) >= 1


@pytest.mark.asyncio
async def test_run_agent_with_custom_max_iterations():
    with tempfile.TemporaryDirectory() as d:
        config = AgentConfig(id="test", name="Test", role="worker",
                             system_prompt="You are a helpful assistant.",
                             tools=[], agent_dir=d)
        result = await run_agent(config, FakeLLM(), "Hello", max_iterations=1)
        assert len(result) > 0
