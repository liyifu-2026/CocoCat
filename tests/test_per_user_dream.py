import sys, os, json, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from dream import get_user_memory_dir, append_user_history, get_unprocessed_history, _user_hash, _read_cursor

def _clean_test_a_users():
    base = os.path.join(os.path.dirname(__file__), "..", "py-agent", "..", "agents", "test_a", "memory", "users")
    if os.path.exists(base):
        shutil.rmtree(base)

def test_get_user_memory_dir():
    d = get_user_memory_dir("test_agent", "abc123")
    assert "users" in d
    assert "abc123" in d

def test_append_and_read_user_history():
    _clean_test_a_users()
    os.makedirs(get_user_memory_dir("test_a", "uh1"), exist_ok=True)
    append_user_history("test_a", "uh1", {"role": "user", "content": "hello"})
    entries, total = get_unprocessed_history("test_a", user_hash="uh1")
    assert len(entries) == 1
    assert entries[0]["content"] == "hello"

def test_user_dream_cursor_independent():
    _clean_test_a_users()
    os.makedirs(get_user_memory_dir("test_a", "u1"), exist_ok=True)
    os.makedirs(get_user_memory_dir("test_a", "u2"), exist_ok=True)
    append_user_history("test_a", "u1", {"content": "msg1"})
    append_user_history("test_a", "u2", {"content": "other"})
    entries_u1, _ = get_unprocessed_history("test_a", user_hash="u1")
    entries_u2, _ = get_unprocessed_history("test_a", user_hash="u2")
    assert len(entries_u1) == 1
    assert len(entries_u2) == 1

def test_user_hash_consistency():
    h1 = _user_hash("user_abc")
    h2 = _user_hash("user_abc")
    assert h1 == h2
    assert len(h1) == 16

def test_read_cursor_default():
    tmp = tempfile.mkdtemp()
    cursor = _read_cursor(os.path.join(tmp, "nonexistent"))
    assert cursor == 0
    shutil.rmtree(tmp)
