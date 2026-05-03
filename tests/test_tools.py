import sys, os, json
from unittest.mock import patch, mock_open
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

from tools import HireAgentTool, _tokenize


def test_hire_agent_tool_pending():
    written_pieces = []

    def track_write(data):
        written_pieces.append(data)
        return len(data)

    m = mock_open()
    m().write.side_effect = track_write

    with patch("builtins.open", m):
        with patch("os.makedirs"):
            tool = HireAgentTool()
            result = tool.execute(
                id="employee_new",
                name="新员工",
                role="资深工程师",
                objective="执行严格的代码审查",
                traits=["细心", "语气:专业"],
                background="10年工作经验",
                rules=["代码必须经过review才能合并"],
            )

    written = "".join(written_pieces)
    data = json.loads(written)

    assert data["id"] == "employee_new"
    assert data["name"] == "新员工"
    assert data["scene"] == "development"
    assert data["status"] == "pending"
    assert data["profile"]["role"] == "资深工程师"
    assert data["profile"]["objective"] == "执行严格的代码审查"
    assert data["profile"]["traits"] == ["细心", "语气:专业"]
    assert data["profile"]["background"] == "10年工作经验"
    assert data["profile"]["rules"] == ["代码必须经过review才能合并"]

    call_path = m.call_args[0][0]
    assert "pending" in call_path
    assert "employee_new.json" in call_path

    assert result.startswith("Hire request created")


def test_tokenize_query():
    tokens = _tokenize("服务器部署配置")
    assert "部署" in tokens
    assert "配置" in tokens
    tokens2 = _tokenize("How to deploy")
    assert "how" in tokens2
    assert "deploy" in tokens2
