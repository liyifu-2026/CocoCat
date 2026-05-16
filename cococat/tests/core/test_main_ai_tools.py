"""Tests for create_main_ai_tools() — Coco has DAG orchestration + memory + meta ONLY."""


def test_main_ai_has_orchestration_tools():
    """Coco must have DAG orchestration tools."""
    from cococat.core.tools import create_main_ai_tools

    tools = create_main_ai_tools()
    names = {t["name"] for t in tools}

    required = {
        "define_dag", "dispatch_task", "check_tasks",
        "append_stage", "update_dag", "stop_task",
        "recall", "pin", "unpin", "record_experience", "recall_experience",
        "todo_write", "cron", "wait", "current_status",
    }
    missing = required - names
    assert not missing, f"Coco missing orchestration tools: {missing}"


def test_main_ai_has_no_direct_tools():
    """Coco must NOT have any direct execution or read tools."""
    from cococat.core.tools import create_main_ai_tools

    tools = create_main_ai_tools()
    names = {t["name"] for t in tools}

    forbidden = {
        "read_file", "list_dir", "web_search", "web_fetch",
        "write_file", "edit_file", "bash", "glob", "grep", "browser",
        "sub_agent",
    }
    overlap = names & forbidden
    assert not overlap, f"Coco should not have these tools: {overlap}"

