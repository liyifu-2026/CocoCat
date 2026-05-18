"""Tests for AgentConfig and load_agent_config."""
import os
import tempfile
import pytest
from cococat.core.agent import AgentConfig, load_agent_config


def test_agent_config_is_immutable():
    config = AgentConfig(
        id="test", name="Test", role="worker",
        system_prompt="You are helpful.",
        tools=[{"name": "bash"}],
        agent_dir="/tmp",
    )
    assert config.id == "test"
    assert config.name == "Test"
    assert config.role == "worker"
    assert config.system_prompt == "You are helpful."
    assert config.tools == [{"name": "bash"}]
    assert config.agent_dir == "/tmp"

    with pytest.raises(Exception):
        config.id = "changed"


def test_agent_config_defaults():
    config = AgentConfig(
        id="a", name="A", role="worker",
        system_prompt="Hi", agent_dir="/tmp",
    )
    assert config.tools == []


def test_load_agent_config_minimal():
    with tempfile.TemporaryDirectory() as d:
        config = load_agent_config(d)
        assert config.agent_dir == d
        assert isinstance(config.system_prompt, str)
        assert len(config.system_prompt) > 0


def test_load_agent_config_with_base_tools():
    with tempfile.TemporaryDirectory() as d:
        tools = [{"name": "bash", "description": "Run bash"}]
        config = load_agent_config(d, base_tools=tools)
        assert config.tools == tools
