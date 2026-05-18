"""Test agent role permissions: RESIDENT vs WORKER, resident tools vs worker tools."""
from cococat.core.agent import AgentRole
from cococat.core.tools import create_resident_tools, create_core_tools


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
