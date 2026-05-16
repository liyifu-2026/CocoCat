"""Test agent role permissions: RESIDENT vs WORKER, resident tools vs worker tools."""
import pytest
from cococat.core.agent import Agent, AgentRole
from cococat.core.tools import create_resident_tools, create_core_tools


class StubLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return type('obj', (object,), {'content': 'ok', 'tool_calls': None})()


@pytest.fixture
def stub_llm():
    return StubLLM()


def test_resident_role_cannot_bind_scene(stub_llm):
    agent = Agent(id="test", name="Test", role=AgentRole.RESIDENT, llm=stub_llm)
    with pytest.raises(ValueError, match="cannot bind"):
        agent.bind_to_scene("test-scene")


def test_worker_role_can_bind_scene(stub_llm):
    agent = Agent(id="test", name="Test", role=AgentRole.WORKER, llm=stub_llm)
    agent.bind_to_scene("test-scene")
    assert agent.bound_scene == "test-scene"


def test_kb_agent_has_admin_tools():
    tools = create_resident_tools(is_kb_agent=True)
    names = [t["name"] for t in tools]
    assert "write_wiki" in names
    assert "search_kb" in names
    assert "read_wiki" in names
    assert "run_dedup" in names
    assert "run_lint" in names
    assert "gen_overview" in names
    assert "cascade_del" in names
    assert "get_graph" in names
    assert "call_worker" in names


def test_coco_resident_has_read_only_kb():
    tools = create_resident_tools(is_kb_agent=False)
    names = [t["name"] for t in tools]
    assert "search_kb" in names
    assert "read_wiki" in names
    assert "write_wiki" not in names
    assert "run_dedup" not in names
    assert "call_worker" in names


def test_worker_has_read_only_kb():
    tools = create_core_tools()
    names = [t["name"] for t in tools]
    assert "search_kb" in names
    assert "read_wiki" in names
    assert "write_wiki" not in names
    assert "run_dedup" not in names
    assert "bash" in names
