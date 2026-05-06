import pytest
import tempfile
import os
import sys
import json
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mailbox import send_message, read_inbox, mark_read
from tools import SendMessageTool


@pytest.fixture
def mailbox_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestMailboxSendMessage:
    def test_send_message_writes_to_inbox(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            result = send_message("employee_a", "employee_b", "Hello from B to A")
            assert "Message sent" in result

            inbox = read_inbox("employee_a")
            assert len(inbox) == 1
            assert inbox[0]["from"] == "employee_b"
            assert inbox[0]["content"] == "Hello from B to A"
            assert inbox[0]["status"] == "unread"

    def test_send_message_creates_directory(self, mailbox_dir):
        nested = os.path.join(mailbox_dir, "nonexistent_agent")
        with patch("mailbox._mailbox_dir", return_value=nested):
            result = send_message("nonexistent_agent", "leader", "test")
            assert "Message sent" in result
            assert os.path.exists(os.path.join(nested, "inbox.jsonl"))

    def test_send_message_multiple_messages(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            send_message("employee_a", "leader", "msg 1")
            send_message("employee_a", "employee_b", "msg 2")
            send_message("employee_a", "leader", "msg 3")

            inbox = read_inbox("employee_a")
            assert len(inbox) == 3
            assert inbox[0]["content"] == "msg 1"
            assert inbox[1]["content"] == "msg 2"
            assert inbox[2]["content"] == "msg 3"

    def test_send_message_empty_content(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            result = send_message("employee_a", "leader", "")
            assert "Message sent" in result

            inbox = read_inbox("employee_a")
            assert len(inbox) == 1
            assert inbox[0]["content"] == ""

    def test_send_message_uses_correct_timestamp_format(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            from datetime import datetime
            send_message("employee_a", "leader", "test")
            inbox = read_inbox("employee_a")
            # verify timestamp is ISO format
            ts = inbox[0]["timestamp"]
            datetime.fromisoformat(ts)


class TestMailboxReadInbox:
    def test_read_inbox_empty(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            inbox = read_inbox("employee_a")
            assert inbox == []

    def test_read_inbox_nonexistent_directory(self, mailbox_dir):
        nonexistent = os.path.join(mailbox_dir, "does_not_exist")
        with patch("mailbox._mailbox_dir", return_value=nonexistent):
            inbox = read_inbox("employee_a")
            assert inbox == []

    def test_read_inbox_preserves_order(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            send_message("employee_a", "leader", "first")
            send_message("employee_a", "employee_b", "second")
            send_message("employee_a", "leader", "third")

            inbox = read_inbox("employee_a")
            assert [m["content"] for m in inbox] == ["first", "second", "third"]

    def test_read_inbox_metadata(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            send_message("employee_a", "leader", "hello")
            inbox = read_inbox("employee_a")
            msg = inbox[0]
            assert "from" in msg
            assert "content" in msg
            assert "timestamp" in msg
            assert "status" in msg
            assert msg["status"] == "unread"


class TestMailboxMarkRead:
    def test_mark_read_updates_status(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            send_message("employee_a", "leader", "test message")
            result = mark_read("employee_a", 0)
            assert "marked as read" in result

            inbox = read_inbox("employee_a")
            assert inbox[0]["status"] == "read"

    def test_mark_read_invalid_index(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            send_message("employee_a", "leader", "test")
            result = mark_read("employee_a", 99)
            assert "out of range" in result

    def test_mark_read_empty_inbox(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            result = mark_read("employee_a", 0)
            assert "empty" in result.lower()


class TestSendMessageTool:
    def test_tool_execute_sends_message(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            tool = SendMessageTool(from_agent="leader")
            result = tool.execute(to="employee_a", message="Hello from leader")
            assert "Message sent" in result

            inbox = read_inbox("employee_a")
            assert len(inbox) == 1
            assert inbox[0]["from"] == "leader"
            assert inbox[0]["content"] == "Hello from leader"

    def test_tool_schema(self):
        tool = SendMessageTool(from_agent="leader")
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        params = schema["function"]["parameters"]["properties"]
        assert "to" in params
        assert "message" in params
        assert schema["function"]["name"] == "send_message"
        assert "Send a message to another agent" in schema["function"]["description"]

    def test_tool_without_from_agent(self, mailbox_dir):
        with patch("mailbox._mailbox_dir", return_value=mailbox_dir):
            tool = SendMessageTool()  # no from_agent
            result = tool.execute(to="employee_a", message="test")
            assert "Message sent" in result

            inbox = read_inbox("employee_a")
            assert inbox[0]["from"] == ""

    def test_tool_multiple_agents_independent(self, mailbox_dir):
        with patch("mailbox._mailbox_dir") as mock_dir:
            def side_effect(agent_id):
                return os.path.join(mailbox_dir, agent_id)
            mock_dir.side_effect = side_effect

            tool_a = SendMessageTool(from_agent="employee_a")
            tool_b = SendMessageTool(from_agent="employee_b")

            tool_a.execute(to="leader", message="from A")
            tool_b.execute(to="leader", message="from B")

            leader_inbox = read_inbox("leader")
            assert len(leader_inbox) == 2
            assert leader_inbox[0]["from"] == "employee_a"
            assert leader_inbox[1]["from"] == "employee_b"

    def test_tool_permission_mode(self):
        tool = SendMessageTool(from_agent="leader")
        from tools import PermissionMode
        assert tool.required_permission == PermissionMode.FULL_ACCESS
