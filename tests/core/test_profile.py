"""Tests for agent profile loader."""
import os
import tempfile
import pytest
from cococat.core.agent_builder import load_agent_profile, profile_to_system_prompt, load_agent_system_prompt


def test_load_profile_from_yaml():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "profile.yaml"), "w") as f:
            f.write("name: CustomerBot\nrole: sub\npersonality: Friendly and helpful\nidentity: I help customers.\n")

        profile = load_agent_profile(d)
        assert profile["name"] == "CustomerBot"
        assert profile["role"] == "sub"
        assert profile["personality"] == "Friendly and helpful"
        assert "I help customers" in profile["identity"]


def test_load_profile_from_identity_md():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "identity.md"), "w") as f:
            f.write("# SupportBot\n\nI am a support agent. Be polite and concise.")

        profile = load_agent_profile(d)
        assert profile["name"] == "SupportBot"
        assert "support agent" in profile.get("identity", "")


def test_load_profile_yaml_takes_priority():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "profile.yaml"), "w") as f:
            f.write("name: YamlBot\nrole: main")
        with open(os.path.join(d, "identity.md"), "w") as f:
            f.write("# MarkdownBot\nI am md.")

        profile = load_agent_profile(d)
        assert profile["name"] == "YamlBot"  # yaml wins


def test_load_profile_defaults():
    with tempfile.TemporaryDirectory() as d:
        profile = load_agent_profile(d)
        assert "name" in profile
        assert profile["role"] == "sub"


def test_profile_to_system_prompt_full():
    profile = {
        "name": "Helper",
        "role": "sub",
        "identity": "I assist with coding.",
        "personality": "Patient and thorough.",
    }
    prompt = profile_to_system_prompt(profile)
    assert "Your name is Helper" in prompt
    assert "Your role: sub" in prompt
    assert "I assist with coding" in prompt
    assert "Patient and thorough" in prompt


def test_profile_to_system_prompt_minimal():
    prompt = profile_to_system_prompt({"name": "Min"})
    assert "Your name is Min" in prompt
    assert "role" not in prompt.lower()


def test_load_agent_system_prompt():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "profile.yaml"), "w") as f:
            f.write("name: TestAgent\nrole: main\nidentity: I am test.\n")

        prompt = load_agent_system_prompt(d)
        assert "TestAgent" in prompt
        assert "I am test" in prompt
