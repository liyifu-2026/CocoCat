import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))
from dream import should_trigger_dream

def make_entries(count: int, chars_per: int = 100) -> list[dict]:
    return [{"content": "x" * chars_per}] * count

def test_trigger_by_count():
    assert should_trigger_dream(make_entries(5), 0, 1000)

def test_not_trigger_below_threshold():
    assert not should_trigger_dream(make_entries(1), 0, 1000)

def test_trigger_by_time():
    assert should_trigger_dream(make_entries(1), 0, 2000)

def test_not_trigger_within_cooldown():
    assert not should_trigger_dream(make_entries(5), 1000, 1100)

def test_trigger_token_budget_large():
    entries = [{"content": "x" * 5000}] * 2
    assert should_trigger_dream(entries, 100, 200)

def test_empty_entries():
    assert not should_trigger_dream([], 0, 1000)
