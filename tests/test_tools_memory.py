import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from tools import RememberTool, RecallTool


def test_remember_tool_global():
    tool = RememberTool()
    result = tool.execute(agent_id="test_a", content="global fact")
    assert isinstance(result, str)
    assert "Remembered" in result


def test_remember_tool_user():
    tool = RememberTool()
    result = tool.execute(agent_id="test_a", content="user fact", user_id="user_abc")
    assert isinstance(result, str)
    assert "user profile" in result


def test_recall_tool_global():
    tool = RecallTool()
    result = tool.execute(agent_id="test_a")
    assert isinstance(result, str)
