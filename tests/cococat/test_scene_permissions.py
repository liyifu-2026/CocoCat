"""Tests for scene permission scoping."""
import os
import tempfile
import pytest
from cococat.core.agent import Agent, AgentRole
from cococat.core.tools import create_core_tools
from cococat.scene.config import SceneConfig


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return {"content": "ok"}


@pytest.fixture
def agent():
    return Agent("agent_c", "Agent C", AgentRole.SUB, FakeLLM(),
                 tools=create_core_tools(),
                 system_prompt="Default context.")


@pytest.fixture(autouse=True)
def _setup_test_skills():
    """Create mock skill files so load_scene_skills finds them."""
    skills_dir = "skills/scenes/test-scene"
    os.makedirs(skills_dir, exist_ok=True)
    with open(os.path.join(skills_dir, "refund_procedure.md"), "w") as f:
        f.write("---\nname: refund_procedure\ndescription: Refund\n---\n# Body")
    with open(os.path.join(skills_dir, "crm_lookup.md"), "w") as f:
        f.write("---\nname: crm_lookup\ndescription: CRM\n---\n# Body")
    yield
    # Cleanup
    try:
        os.remove(os.path.join(skills_dir, "refund_procedure.md"))
        os.remove(os.path.join(skills_dir, "crm_lookup.md"))
        os.rmdir(skills_dir)
    except OSError:
        pass


@pytest.fixture
def scene():
    return SceneConfig(
        id="test-scene",
        name="Test Scene",
        context="You help customers with refunds.",
        kbs=["product-manual", "faq"],
    )


def test_agent_has_all_tools_before_binding(agent):
    tools = agent.get_tools()
    names = {t["name"] for t in tools}
    assert "read_file" in names
    assert "bash" in names  # core tools present


def test_agent_scoped_after_binding(agent, scene):
    agent.bind_to_scene(scene)
    assert agent.state.value == "working"
    assert agent.bound_scene == "test-scene"

    # System prompt should include scene context
    assert "refunds" in agent._system_prompt

    # Tools should include scene skills
    tools = agent.get_tools()
    names = {t["name"] for t in tools}

    # Core tools still present
    assert "read_file" in names
    assert "bash" in names

    # Scene skills loaded from disk
    assert "refund_procedure" in names
    assert "crm_lookup" in names


def test_agent_unbind_restores_default(agent, scene):
    agent.bind_to_scene(scene)
    agent.unbind()

    assert agent.state.value == "idle"
    assert agent.bound_scene is None
    assert agent._system_prompt == "Default context."

    tools = agent.get_tools()
    names = {t["name"] for t in tools}
    assert "refund_procedure" not in names  # Scene skills removed
    assert "read_file" in names  # Core tools present


def test_agent_kb_access_allowed(agent, scene):
    """Scene-bound agent can read files within its scene's KBs."""
    # Create test KB
    os.makedirs("knowledge/product-manual", exist_ok=True)
    with open("knowledge/product-manual/test.md", "w") as f:
        f.write("KB content")

    agent.bind_to_scene(scene)
    tools = {t["name"]: t for t in agent.get_tools()}

    result = tools["read_file"]["execute"](
        {"path": "knowledge/product-manual/test.md"}, {}
    )
    assert "KB content" in str(result)

    agent.unbind()
    os.remove("knowledge/product-manual/test.md")


def test_agent_kb_access_denied(agent, scene):
    """Scene-bound agent canNOT read files outside its scene's KBs."""
    agent.bind_to_scene(scene)
    tools = {t["name"]: t for t in agent.get_tools()}

    # agent's scene only has product-manual, faq — not team-wiki
    result = tools["read_file"]["execute"](
        {"path": "knowledge/team-wiki/test.md"}, {}
    )
    assert "access denied" in str(result).lower()

    agent.unbind()


def test_agent_write_only_workspace(agent, scene):
    """Scene-bound agent can write to workspace but not KB dir."""
    agent.bind_to_scene(scene)
    tools = {t["name"]: t for t in agent.get_tools()}

    # Write to workspace — allowed
    result = tools["write_file"]["execute"](
        {"path": "workspace/notes.md", "content": "test"}, {}
    )
    assert "error" not in str(result).lower()

    # Write to KB — denied
    result = tools["write_file"]["execute"](
        {"path": "knowledge/product-manual/test.md", "content": "test"}, {}
    )
    assert "access denied" in str(result).lower()

    agent.unbind()


def test_main_ai_cannot_bind_to_scene():
    main = Agent("main", "Main AI", AgentRole.MAIN, FakeLLM())
    with pytest.raises(ValueError):
        main.bind_to_scene(SceneConfig(id="cs", name="CS"))
