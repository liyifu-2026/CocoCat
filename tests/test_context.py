import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from context import build_system_prompt, build_tool_descriptions, load_scene_context, load_agent_profile, _build_profile_section


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


def test_load_agent_profile():
    profile_data = {
        "role": "资深工程师",
        "objective": "执行严格的代码审查",
        "traits": ["细心", "语气:专业"],
        "background": "10年工作经验",
        "rules": ["代码必须经过review才能合并"],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = os.path.join(tmpdir, "py-agent")
        os.makedirs(base_dir)
        agents_dir = os.path.join(tmpdir, "agents", "test-agent")
        os.makedirs(agents_dir)
        with open(os.path.join(agents_dir, "profile.json"), "w", encoding="utf-8") as f:
            json.dump(profile_data, f)
        result = load_agent_profile("test-agent", base_dir=base_dir)
    assert result == profile_data


def test_load_agent_profile_missing():
    result = load_agent_profile("nonexistent_agent_xyz")
    assert result is None


def test_build_system_prompt_with_profile():
    profile = {
        "role": "资深工程师",
        "objective": "执行严格的代码审查",
        "traits": ["细心", "语气:专业"],
        "background": "10年工作经验",
        "rules": ["代码必须经过review才能合并"],
    }
    prompt = build_system_prompt(agent_name="TestAgent", profile=profile)
    assert "## Agent Profile" in prompt
    assert "资深工程师" in prompt
    assert "执行严格的代码审查" in prompt
    assert "细心, 语气:专业" in prompt
    assert "10年工作经验" in prompt
    assert "代码必须经过review才能合并" in prompt


def test_build_system_prompt_without_profile():
    prompt = build_system_prompt(agent_name="TestAgent")
    assert "## Agent Profile" not in prompt


def test_build_profile_section():
    profile = {"role": "Dev", "objective": "Code", "traits": ["fast"], "background": "Exp", "rules": ["Be safe"]}
    section = _build_profile_section(profile)
    assert "- Role: Dev" in section
    assert "- Objective: Code" in section
    assert "- Traits: fast" in section
    assert "- Background: Exp" in section
    assert "- Rules:" in section
    assert "  - Be safe" in section
