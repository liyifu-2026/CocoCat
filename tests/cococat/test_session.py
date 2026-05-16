"""Tests for cococat.core.session."""
import os
import tempfile
import pytest
from cococat.core.session import Session, SessionManager


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def session_mgr():
    return SessionManager(max_cached=3)


@pytest.mark.asyncio
async def test_session_create_writes_jsonl(tmp_dir, session_mgr):
    session = await session_mgr.create(tmp_dir, system_prompt="You are helpful.")
    path = os.path.join(tmp_dir, f"{session.id}.jsonl")
    assert os.path.exists(path)

    with open(path) as f:
        lines = f.readlines()
    assert len(lines) >= 1  # at least system prompt


@pytest.mark.asyncio
async def test_session_append_and_read(tmp_dir, session_mgr):
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Hello")
    await session.append("assistant", "Hi there!")

    messages = await session.read()
    assert len(messages) >= 2
    assert messages[-2] == {"role": "user", "content": "Hello"}
    assert messages[-1] == {"role": "assistant", "content": "Hi there!"}


@pytest.mark.asyncio
async def test_session_round_trip(tmp_dir, session_mgr):
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Test message")
    session_id = session.id

    # Load from disk
    loaded = await session_mgr.open(str(session_id), tmp_dir)
    messages = await loaded.read()
    assert any(m["content"] == "Test message" for m in messages)


@pytest.mark.asyncio
async def test_lru_eviction(tmp_dir, session_mgr):
    sessions = []
    for i in range(5):
        s = await session_mgr.create(tmp_dir)
        await s.append("user", f"msg {i}")
        sessions.append(s)

    # Should have 3 cached (max_cached=3), first 2 evicted
    cached_count = len(session_mgr._cache)
    assert cached_count <= 3


@pytest.mark.asyncio
async def test_session_close_persists(tmp_dir, session_mgr):
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Before close")
    await session.close()

    # Re-open and verify
    loaded = await session_mgr.open(session.id, tmp_dir)
    messages = await loaded.read()
    assert any(m["content"] == "Before close" for m in messages)


@pytest.mark.asyncio
async def test_multiple_sessions_independent(tmp_dir, session_mgr):
    s1 = await session_mgr.create(tmp_dir)
    s2 = await session_mgr.create(tmp_dir)

    await s1.append("user", "S1 message")
    await s2.append("user", "S2 message")

    m1 = await s1.read()
    m2 = await s2.read()

    assert any(m["content"] == "S1 message" for m in m1)
    assert any(m["content"] == "S2 message" for m in m2)
    assert not any(m["content"] == "S2 message" for m in m1)


@pytest.mark.asyncio
async def test_session_append_after_close_raises(tmp_dir, session_mgr):
    session = await session_mgr.create(tmp_dir)
    await session.close()
    with pytest.raises(RuntimeError, match="closed"):
        await session.append("user", "should fail")


@pytest.mark.asyncio
async def test_session_read_on_nonexistent_file(tmp_dir):
    from cococat.core.session import Session
    s = Session("nonexistent", tmp_dir)
    messages = await s.read()
    assert messages == []


@pytest.mark.asyncio
async def test_session_sanitized_read_filters_roles(tmp_dir, session_mgr):
    """sanitized_read() returns only user/assistant messages, skipping system/tool."""
    session = await session_mgr.create(tmp_dir, system_prompt="You are helpful.")
    await session.append("user", "Hello")
    await session.append("assistant", "Hi")
    await session.append("tool", "tool result")
    await session.append("user", "Thanks")

    messages = await session.sanitized_read()
    assert len(messages) == 3  # system (filtered) + user + assistant + tool (filtered) + user
    roles = {m["role"] for m in messages}
    assert roles == {"user", "assistant"}


@pytest.mark.asyncio
async def test_session_sanitized_read_max_lines(tmp_dir, session_mgr):
    """sanitized_read(max_lines=N) returns only the last N user/assistant messages."""
    session = await session_mgr.create(tmp_dir)
    for i in range(10):
        await session.append("user", f"msg {i}")
        await session.append("assistant", f"reply {i}")

    messages = await session.sanitized_read(max_lines=6)
    assert len(messages) == 6
    assert messages[0]["content"] == "msg 7"
    assert messages[-1]["content"] == "reply 9"


@pytest.mark.asyncio
async def test_session_sanitized_read_nonexistent(tmp_dir):
    """sanitized_read() on nonexistent session returns empty list."""
    from cococat.core.session import Session
    s = Session("nonexistent", tmp_dir)
    messages = await s.sanitized_read()
    assert messages == []


@pytest.mark.asyncio
async def test_session_append_pair(tmp_dir, session_mgr):
    """append_pair() writes user and assistant messages in one call."""
    session = await session_mgr.create(tmp_dir)
    await session.append_pair("Hello", "Hi there!")

    messages = await session.read()
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(user_msgs) == 1
    assert user_msgs[0]["content"] == "Hello"
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] == "Hi there!"


@pytest.mark.asyncio
async def test_session_manager_open_nonexistent(tmp_dir, session_mgr):
    with pytest.raises(FileNotFoundError):
        await session_mgr.open("bad_id", tmp_dir)
