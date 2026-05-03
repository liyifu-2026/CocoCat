import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from tools import create_default_registry


def test_registry_no_old_tools():
    registry = create_default_registry()
    names = [t.name for t in registry.list_tools()]
    old_tools = ["install_skill", "uninstall_skill", "search_skill", "search_kb",
                  "list_installed_skills", "lsp_hover", "lsp_definition", "lsp_references",
                  "revert_memory", "learn_skill", "forget_skill", "list_skills", "skill_manage"]
    for old in old_tools:
        assert old not in names, f"Old tool '{old}' should have been removed"


def test_registry_keeps_core_tools():
    registry = create_default_registry()
    names = [t.name for t in registry.list_tools()]
    core = ["read_file", "write_file", "edit_file", "exec_command", "sub_agent",
            "remember", "recall", "dream", "grep_search", "glob_search",
            "web_fetch", "web_search", "ask_user", "lsp_query"]
    for c in core:
        assert c in names, f"Core tool '{c}' missing"


def test_lsp_query_actions():
    from tools import LspQueryTool
    tool = LspQueryTool()
    assert tool.name == "lsp_query"
    assert "action" in tool.parameters["properties"]
    actions = tool.parameters["properties"]["action"]["enum"]
    assert "hover" in actions
    assert "definition" in actions
    assert "references" in actions
