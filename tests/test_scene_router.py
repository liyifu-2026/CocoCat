import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

import tempfile
import scene_router


def _make_base(tmp):
    return os.path.join(tmp, "scenes")


def test_store_and_get_history():
    with tempfile.TemporaryDirectory() as tmp:
        import scene_router as sr
        sr._BASE = _make_base(tmp)
        sr.store_message("test-scene", "user1", {"content": "hello", "direction": "incoming", "channel_type": "web"})
        sr.store_message("test-scene", "user1", {"content": "hi back", "direction": "outgoing", "channel_type": "web"})
        history = sr.get_history("test-scene", "user1")
        sr._BASE = None
        assert len(history) == 2
        assert history[0]["content"] == "hello"
        assert history[1]["content"] == "hi back"


def test_get_history_empty():
    with tempfile.TemporaryDirectory() as tmp:
        import scene_router as sr
        sr._BASE = _make_base(tmp)
        history = sr.get_history("nonexistent", "user1")
        sr._BASE = None
        assert history == []


def test_store_message_creates_dir():
    with tempfile.TemporaryDirectory() as tmp:
        import scene_router as sr
        sr._BASE = _make_base(tmp)
        sr.store_message("s1", "u1", {"content": "test", "direction": "incoming", "channel_type": "web"})
        expected = os.path.join(tmp, "scenes", "s1", "users", "u1", "history.jsonl")
        sr._BASE = None
        assert os.path.exists(expected)
