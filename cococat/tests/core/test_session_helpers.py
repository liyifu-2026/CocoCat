"""Tests for session module-level helpers."""
import json
import os
from cococat.core.session import load_session, save_session_pair


class TestLoadSession:
    def test_loads_last_n_messages(self, tmp_path):
        path = os.path.join(str(tmp_path), "session.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"role": "user", "content": "hello"}) + "\n")
            f.write(json.dumps({"role": "assistant", "content": "hi"}) + "\n")
            f.write(json.dumps({"role": "user", "content": "how are you"}) + "\n")
            f.write(json.dumps({"role": "assistant", "content": "good"}) + "\n")

        messages = load_session(path, max_lines=2)
        assert len(messages) == 2
        assert messages[0]["content"] == "how are you"
        assert messages[1]["content"] == "good"

    def test_skips_system_and_tool_roles(self, tmp_path):
        path = os.path.join(str(tmp_path), "session.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"role": "system", "content": "you are a bot"}) + "\n")
            f.write(json.dumps({"role": "user", "content": "hello"}) + "\n")
            f.write(json.dumps({"role": "tool", "content": "result"}) + "\n")
            f.write(json.dumps({"role": "assistant", "content": "done"}) + "\n")

        messages = load_session(path)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_empty_file_returns_empty_list(self, tmp_path):
        path = os.path.join(str(tmp_path), "empty.jsonl")
        with open(path, "w") as f:
            f.write("")

        assert load_session(path) == []

    def test_missing_file_returns_empty_list(self, tmp_path):
        assert load_session("/nonexistent/session.jsonl") == []

    def test_malformed_json_skipped(self, tmp_path):
        path = os.path.join(str(tmp_path), "session.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"role": "user", "content": "ok"}) + "\n")
            f.write("not valid json\n")
            f.write(json.dumps({"role": "assistant", "content": "done"}) + "\n")

        messages = load_session(path)
        assert len(messages) == 2


class TestSaveSessionPair:
    def test_appends_user_and_assistant(self, tmp_path):
        path = os.path.join(str(tmp_path), "session.jsonl")
        save_session_pair(path, "hello", "hi there")

        with open(path) as f:
            lines = [json.loads(l) for l in f if l.strip()]

        assert len(lines) == 2
        assert lines[0] == {"role": "user", "content": "hello"}
        assert lines[1] == {"role": "assistant", "content": "hi there"}

    def test_appends_to_existing_file(self, tmp_path):
        path = os.path.join(str(tmp_path), "session.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"role": "user", "content": "first"}) + "\n")

        save_session_pair(path, "second", "reply")

        with open(path) as f:
            lines = [json.loads(l) for l in f if l.strip()]

        assert len(lines) == 3
        assert lines[1]["content"] == "second"

    def test_creates_parent_directories(self, tmp_path):
        path = os.path.join(str(tmp_path), "deep/nested/dir/session.jsonl")
        save_session_pair(path, "a", "b")

        assert os.path.exists(path)
