import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

import tempfile
from unittest.mock import patch, MagicMock
from agent_loop import (
    estimate_tokens, estimate_messages_tokens,
    _snip_history, consolidate, append_history, _microcompact_tool_results
)

def test_estimate_tokens():
    tokens = estimate_tokens("hello world")
    assert tokens > 0

def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0

def test_estimate_messages_tokens():
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    total = estimate_messages_tokens(msgs)
    assert total > 0

def test_snip_history_within_budget():
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "hello"},
    ]
    result = _snip_history(msgs, budget=10000)
    assert len(result) == 2
    assert result == msgs

def test_snip_history_over_budget():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello " * 1000},
        {"role": "assistant", "content": "hi " * 1000},
        {"role": "user", "content": "how are you " * 1000},
    ]
    result = _snip_history(msgs, budget=500)
    assert len(result) <= 4
    assert result[0]["role"] == "system"

def test_snip_history_preserves_recent():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "a " * 2000},
        {"role": "assistant", "content": "b " * 2000},
        {"role": "user", "content": "latest"},
    ]
    result = _snip_history(msgs, budget=500)
    contents = [m.get("content", "") for m in result]
    assert any("latest" in c for c in contents)

def test_microcompact_tool_results_truncates():
    msgs = [
        {"role": "tool", "content": "x" * 5000},
    ]
    result = _microcompact_tool_results(msgs, max_tool_chars=100)
    assert len(result[0]["content"]) < 200
    assert "truncated" in result[0]["content"]

def test_microcompact_tool_results_short_unchanged():
    msgs = [
        {"role": "tool", "content": "short result"},
    ]
    result = _microcompact_tool_results(msgs, max_tool_chars=2000)
    assert result[0]["content"] == "short result"

def test_consolidate_within_budget():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    result = consolidate(msgs, MagicMock(), budget=10000)
    assert len(result) >= 3

def test_consolidate_over_budget():
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "a " * 1000},
        {"role": "assistant", "content": "b " * 1000},
        {"role": "user", "content": "c " * 1000},
        {"role": "assistant", "content": "d " * 1000},
    ]
    mock_llm = MagicMock()
    mock_llm.chat.return_value = {"content": "summary text"}
    result = consolidate(msgs, mock_llm, budget=100)
    assert result[0]["role"] == "system"
    assert any("[Consolidated]" in (m.get("content", "") or "") for m in result)

def test_append_history():
    with tempfile.TemporaryDirectory() as tmp:
        import agent_loop
        fake_pyagent = os.path.join(tmp, "py-agent")
        os.makedirs(fake_pyagent)
        orig_file = agent_loop.__file__
        try:
            agent_loop.__file__ = os.path.join(fake_pyagent, "agent_loop.py")
            append_history("test-agent", "prompt text", "response text", 3)
            hist_path = os.path.join(tmp, "agents", "test-agent", "memory", "history.jsonl")
            assert os.path.exists(hist_path)
            with open(hist_path) as f:
                data = json.loads(f.readline())
            assert data["prompt"] == "prompt text"
            assert data["response_summary"] == "response text"
            assert data["iterations"] == 3
        finally:
            agent_loop.__file__ = orig_file
