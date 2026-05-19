"""Tests for prompt builder with memory."""
import os
import tempfile
import pytest
from cococat.core.agent_builder import build_system_prompt, load_memory_from_agent_dir
from cococat.core.agent import Agent, AgentRole
from cococat.providers.base import LLMResponse


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content="ok")


def test_load_memory_from_agent_dir():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "memory"))
        with open(os.path.join(d, "memory", "memory.md"), "w") as f:
            f.write("- User prefers short answers\n- Project: CocoCat v2")

        memory, pinned = load_memory_from_agent_dir(d)
        assert "short answers" in memory
        assert pinned == ""


def test_agent_inits_with_memory():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "memory"))
        with open(os.path.join(d, "memory", "memory.md"), "w") as f:
            f.write("- User is a Python developer")

        agent = Agent("test", "Test", AgentRole.WORKER, FakeLLM(), agent_dir=d)
        assert "Python developer" in agent.config.system_prompt


def test_build_prompt_with_memory():
    prompt = build_system_prompt(
        agent_profile="Test Agent",
        memory_content="- User likes brevity",
        pinned_facts="- Important: deadline Friday",
    )
    assert "Test Agent" in prompt
    assert "brevity" in prompt
    assert "deadline Friday" in prompt
