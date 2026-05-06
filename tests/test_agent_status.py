"""Tests for agent_status — file-based storage (_status.json)."""
import sys, os, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

import agent_status as st


class TestAgentStatus:
    def _patch_file(self, tmp):
        path = os.path.join(tmp, "status.json")
        st.set_status_file(path)
        return path

    def test_report_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._patch_file(tmp)
            st.report("alice", "running", "processing task")
            result = st.get_status("alice")
            assert result["agent_id"] == "alice"
            assert result["status"] == "running"
            assert result["detail"] == "processing task"
            assert result["updated_at"] != ""

    def test_get_unknown_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._patch_file(tmp)
            result = st.get_status("nonexistent")
            assert result["agent_id"] == "nonexistent"
            assert result["status"] == "unknown"

    def test_list_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._patch_file(tmp)
            st.report("alice", "running", "working")
            st.report("bob", "idle", "waiting")
            all_status = st.list_all()
            assert "alice" in all_status
            assert "bob" in all_status
            assert all_status["alice"]["status"] == "running"
            assert all_status["bob"]["status"] == "idle"

    def test_report_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._patch_file(tmp)
            st.report("alice", "running", "first")
            st.report("alice", "done", "second")
            result = st.get_status("alice")
            assert result["status"] == "done"
            assert result["detail"] == "second"

    def test_detect_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._patch_file(tmp)
            st.report("alice", "running", "fresh")
            time.sleep(0.01)
            st.report("bob", "running", "fresh")
            stale = st.detect_stale(timeout=0)
            assert "alice" in stale
            assert "bob" in stale
            stale_long = st.detect_stale(timeout=99999)
            assert len(stale_long) == 0

    def test_set_status_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = self._patch_file(tmp)
            st.report("alice", "running", "test")
            assert os.path.exists(p1)
            result = st.get_status("alice")
            assert result["status"] == "running"
