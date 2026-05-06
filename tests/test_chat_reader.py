"""Tests for chat_reader — file-based storage (JSONL)."""
import sys, os, json, tempfile, unittest.mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

import chat_reader as cr


def _setup(tmp: str):
    """Create chat/groups.json + chat/{group}/messages.jsonl under tmp/chat/."""
    base = os.path.join(tmp, "chat")
    os.makedirs(base)
    groups = {
        "groups": [
            {"id": "team-alpha", "name": "Team Alpha",
             "members": [{"id": "agent1", "name": "Agent 1"}, {"id": "leader", "name": "Leader"}],
             "announcement": ""},
            {"id": "general", "name": "General",
             "members": [{"id": "agent1", "name": "Agent 1"}, {"id": "bob", "name": "Bob"}, {"id": "leader", "name": "Leader"}],
             "announcement": ""},
        ]
    }
    with open(os.path.join(base, "groups.json"), "w") as f:
        json.dump(groups, f)

    for gid, msgs in [
        ("team-alpha", [
            {"from": "leader", "content": "Hey @agent1, check this", "timestamp": "T1", "recalled": False, "read_by": []},
            {"from": "bob", "content": "Low priority note", "timestamp": "T2", "recalled": False, "read_by": []},
        ]),
        ("general", [
            {"from": "leader", "content": "@all meeting time", "timestamp": "T3", "recalled": False, "read_by": []},
            {"from": "bob", "content": "Hello everyone", "timestamp": "T4", "recalled": False, "read_by": []},
        ]),
    ]:
        d = os.path.join(base, gid)
        os.makedirs(d)
        with open(os.path.join(d, "messages.jsonl"), "w") as f:
            for m in msgs:
                f.write(json.dumps(m) + "\n")


def _patch(tmp: str):
    """Patch BASE so reader looks under tmp/chat/."""
    pyagent = os.path.join(tmp, "py-agent")
    os.makedirs(pyagent, exist_ok=True)
    return unittest.mock.patch.object(cr, "BASE", pyagent)


class TestGetUnreadMessages:
    def test_finds_mention(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup(tmp)
            with _patch(tmp):
                unread = cr.get_unread_messages("agent1")
        assert len(unread) >= 1
        assert any("@agent1" in u["content"] and u["score"] >= 100 for u in unread)

    def test_finds_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup(tmp)
            with _patch(tmp):
                unread = cr.get_unread_messages("agent1")
        assert any("@all" in u["content"] and u["score"] >= 80 for u in unread)

    def test_skips_low_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup(tmp)
            with _patch(tmp):
                unread = cr.get_unread_messages("agent1")
        assert all("Low priority" not in u["content"] for u in unread)

    def test_non_member_sees_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup(tmp)
            with _patch(tmp):
                unread = cr.get_unread_messages("outsider")
        assert len(unread) == 0

    def test_returns_full_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup(tmp)
            with _patch(tmp):
                unread = cr.get_unread_messages("agent1")
        assert len(unread) > 0
        for u in unread:
            assert "group_id" in u and "group_name" in u
            assert "msg_index" in u and "from" in u
            assert "content" in u and "score" in u and "msg" in u

    def test_skips_recalled(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "chat")
            os.makedirs(os.path.join(base, "team-alpha"))
            with open(os.path.join(base, "groups.json"), "w") as f:
                json.dump({"groups": [{"id": "team-alpha", "name": "TA", "members": [{"id": "agent1", "name": "A1"}], "announcement": ""}]}, f)
            msgs = [
                {"from": "leader", "content": "@agent1 important", "timestamp": "T1", "recalled": False, "read_by": []},
                {"from": "leader", "content": "@agent1 recalled", "timestamp": "T2", "recalled": True, "read_by": []},
            ]
            with open(os.path.join(base, "team-alpha", "messages.jsonl"), "w") as f:
                for m in msgs:
                    f.write(json.dumps(m) + "\n")
            with _patch(tmp):
                unread = cr.get_unread_messages("agent1")
        assert len(unread) == 1
        assert "recalled" not in unread[0]["content"]


class TestMarkAsRead:
    def _unread_with_target(self, tmp):
        with _patch(tmp):
            unread = cr.get_unread_messages("agent1")
            assert len(unread) > 0
            return unread[0]

    def _unread_keys(self, tmp):
        _setup(tmp)
        with _patch(tmp):
            u2 = cr.get_unread_messages("agent1")
            return [(x["group_id"], x["msg_index"]) for x in u2]

    def test_adds_read_by_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup(tmp)
            with _patch(tmp):
                target = self._unread_with_target(tmp)
                cr.mark_as_read("agent1", target["group_id"], target["msg_index"], target["score"])
                keys = [(x["group_id"], x["msg_index"]) for x in cr.get_unread_messages("agent1")]
            assert (target["group_id"], target["msg_index"]) not in keys

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup(tmp)
            with _patch(tmp):
                target = self._unread_with_target(tmp)
                cr.mark_as_read("agent1", target["group_id"], target["msg_index"], target["score"])
                cr.mark_as_read("agent1", target["group_id"], target["msg_index"], target["score"])
                keys = [(x["group_id"], x["msg_index"]) for x in cr.get_unread_messages("agent1")]
            assert (target["group_id"], target["msg_index"]) not in keys

    def test_other_agent_not_affected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _setup(tmp)
            with _patch(tmp):
                target = self._unread_with_target(tmp)
                cr.mark_as_read("agent1", target["group_id"], target["msg_index"], target["score"])
                ub = cr.get_unread_messages("leader")
            keys_b = [(x["group_id"], x["msg_index"]) for x in ub]
            assert (target["group_id"], target["msg_index"]) in keys_b
