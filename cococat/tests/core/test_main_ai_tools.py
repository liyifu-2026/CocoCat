"""Tests for create_main_ai_tools() — Coco has DAG + read tools + memory + meta."""


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


def test_main_ai_has_read_tools():
    """Coco CAN directly read and search, but NOT write/execute."""
    from cococat.core.tools import create_main_ai_tools

    tools = create_main_ai_tools()
    names = {t["name"] for t in tools}

    # Coco SHOULD have these
    assert "read_file" in names, "Coco should have read_file"
    assert "web_search" in names, "Coco should have web_search"

    # Coco should NOT have these
    forbidden = {"write_file", "edit_file", "bash", "browser", "sub_agent"}
    overlap = names & forbidden
    assert not overlap, f"Coco has forbidden write/execution tools: {overlap}"
