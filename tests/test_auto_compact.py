import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from auto_compact import should_compact, compact_user_history


def make_large_history(num_entries: int, chars_per: int = 500) -> str:
    lines = []
    for i in range(num_entries):
        lines.append(json.dumps({"content": "x" * chars_per, "ts": i}))
    return "\n".join(lines)


def test_should_compact_small():
    assert not should_compact(make_large_history(5, 100), budget=5000)


def test_should_compact_large():
    assert should_compact(make_large_history(20, 500), budget=5000)


def test_compact_preserves_recent():
    history = make_large_history(15, 500)
    compacted = compact_user_history(history, budget=3000, keep_recent=3)
    lines = compacted.strip().split("\n")
    assert len(lines) >= 3


def test_compact_noop_when_small():
    history = make_large_history(3, 100)
    compacted = compact_user_history(history, budget=5000)
    assert compacted == history


def test_compact_creates_summary():
    history = make_large_history(10, 500)
    compacted = compact_user_history(history, budget=2000, keep_recent=2)
    lines = compacted.strip().split("\n")
    first = json.loads(lines[0])
    assert first["type"] == "compacted_summary"
    assert first["original_count"] > 0


def test_compact_empty():
    assert compact_user_history("") == ""
