import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from tools import RememberTool, RecallTool


def test_remember_tool_global():
    tool = RememberTool(agent_id="test_a")
    result = tool.execute(content="global fact")
    assert isinstance(result, str)
    assert "Remembered" in result


def test_remember_tool_user():
    tool = RememberTool(agent_id="test_a")
    result = tool.execute(content="user fact", user_id="user_abc")
    assert isinstance(result, str)
    assert "user profile" in result


def test_recall_tool_global():
    tool = RecallTool(agent_id="test_a")
    result = tool.execute()
    assert isinstance(result, str)
