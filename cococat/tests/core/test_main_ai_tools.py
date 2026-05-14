"""Tests for create_main_ai_tools() — Main AI gets orchestration tools only."""


def test_main_ai_tools_excludes_execution_tools():
    """Main AI must NOT have write_file, edit_file, bash, glob, grep, browser, sub_agent."""
    from cococat.core.tools import create_main_ai_tools

    tools = create_main_ai_tools()
    names = {t["name"] for t in tools}

    forbidden = {"write_file", "edit_file", "bash", "glob", "grep", "browser", "sub_agent"}
    assert names.isdisjoint(forbidden), f"Main AI should not have: {names & forbidden}"


def test_main_ai_tools_includes_orchestration_tools():
    """Main AI must have orchestration and read-only tools."""
    from cococat.core.tools import create_main_ai_tools

    tools = create_main_ai_tools()
    names = {t["name"] for t in tools}

    required = {
        "define_dag", "append_stage", "update_dag", "dispatch_task",
        "check_tasks", "stop_task",
        "pin", "unpin", "recall", "record_experience", "recall_experience",
        "read_file", "list_dir",
        "web_search", "web_fetch",
        "wait", "current_status", "todo_write",
    }
    missing = required - names
    assert not missing, f"Main AI missing tools: {missing}"


def test_main_ai_tools_subset_of_core_tools():
    """Every main_ai tool must exist in the full core tools."""
    from cococat.core.tools import create_core_tools, create_main_ai_tools

    core_names = {t["name"] for t in create_core_tools()}
    main_names = {t["name"] for t in create_main_ai_tools()}

    extra = main_names - core_names
    assert not extra, f"Main AI has unknown tools: {extra}"
