import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from context import build_system_prompt, build_tool_descriptions, load_scene_context


def test_build_system_prompt_contains_identity():
    prompt = build_system_prompt(agent_id="test-id", agent_name="TestAgent")
    assert "test-id" in prompt
    assert "TestAgent" in prompt


def test_build_system_prompt_contains_scene():
    prompt = build_system_prompt(scene_name="TestScene", scene_context="Test context")
    assert "TestScene" in prompt
    assert "Test context" in prompt


def test_build_system_prompt_contains_memory():
    prompt = build_system_prompt(agent_memory="Some remembered facts")
    assert "Some remembered facts" in prompt


def test_build_system_prompt_contains_skills():
    prompt = build_system_prompt(agent_skills="communication", env_skills="code_review")
    assert "communication" in prompt
    assert "code_review" in prompt


def test_build_tool_descriptions():
    tools = [{"function": {"name": "test_tool", "description": "A test tool",
                           "parameters": {"type": "object", "properties": {"p": {"description": "a param"}}, "required": ["p"]}}}]
    desc = build_tool_descriptions(tools)
    assert "test_tool" in desc
    assert "A test tool" in desc
    assert "p (required)" in desc


def test_load_scene_context_nonexistent():
    name, ctx = load_scene_context("nonexistent_scene_xyz")
    assert name == "nonexistent_scene_xyz"
    assert ctx == ""
