"""Tests for resolve_tools_for_mode("default") — Coco has read tools + memory + meta."""


def test_main_ai_has_orchestration_tools():
    """Coco must have memory and meta tools."""
    from cococat.core.tools import resolve_tools_for_mode

    tools = resolve_tools_for_mode("default")
    names = {t["name"] for t in tools}

    required = {
        "recall", "pin", "unpin",
        "cron", "current_status",
    }
    missing = required - names
    assert not missing, f"Coco missing orchestration tools: {missing}"


def test_main_ai_has_read_tools():
    """Coco CAN directly read and search, but NOT write/execute."""
    from cococat.core.tools import resolve_tools_for_mode

    tools = resolve_tools_for_mode("default")
    names = {t["name"] for t in tools}

    assert "read_file" in names, "Coco should have read_file"
    assert "web_search" in names, "Coco should have web_search"

    forbidden = {"write_file", "edit_file", "bash", "browser"}
    overlap = names & forbidden
    assert not overlap, f"Coco has forbidden write/execution tools: {overlap}"
