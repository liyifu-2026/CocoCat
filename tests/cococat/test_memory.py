"""Tests for memory pipeline."""
import os
import json
import tempfile
import asyncio
import pytest
from cococat.core.session import Session, SessionManager
from cococat.memory.ticker import MemoryTicker
from cococat.memory.facts import FactsExtractor
from cococat.memory.compiler import DailyCompiler
from cococat.db import Database


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        content = messages[-1]["content"]
        if "Extract" in content:
            return {"content": '[{"text": "User prefers short answers", "tags": "preference"}]'}
        return {"content": "Summary: user asked about refund policy."}


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.mark.asyncio
async def test_memory_ticker_summarizes_session(tmp_dir, llm):
    session_mgr = SessionManager()
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Hello")
    await session.append("assistant", "Hi there")
    await session.append("user", "What's the refund policy?")
    await session.append("assistant", "Refund policy: ...")

    ticker = MemoryTicker(llm, session_mgr, memory_dir=os.path.join(tmp_dir, "memory"))

    # Simulate 6 turns to trigger summary
    for i in range(6):
        await ticker.notify_turn(session)

    await asyncio.sleep(0.05)

    # Check summary was written
    summary_path = os.path.join(tmp_dir, "memory", "summaries")
    assert os.path.exists(summary_path)
    files = os.listdir(summary_path)
    assert len(files) == 1
    assert files[0].endswith(".json")


@pytest.mark.asyncio
async def test_memory_ticker_skip_below_threshold(tmp_dir, llm):
    session_mgr = SessionManager()
    session = await session_mgr.create(tmp_dir)

    ticker = MemoryTicker(llm, session_mgr, memory_dir=os.path.join(tmp_dir, "memory"))
    await ticker.notify_turn(session)  # Only 1 turn — no summary yet

    summary_path = os.path.join(tmp_dir, "memory", "summaries")
    assert not os.path.exists(summary_path)


@pytest.mark.asyncio
async def test_memory_ticker_on_session_end(tmp_dir, llm):
    session_mgr = SessionManager()
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Hello")
    await session.append("assistant", "Hi")

    ticker = MemoryTicker(llm, session_mgr, memory_dir=os.path.join(tmp_dir, "memory"))
    await ticker.notify_session_end(session)

    await asyncio.sleep(0.05)

    summary_path = os.path.join(tmp_dir, "memory", "summaries")
    assert os.path.exists(summary_path)


@pytest.mark.asyncio
async def test_memory_ticker_fingerprint_cache(tmp_dir, llm):
    session_mgr = SessionManager()
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "cache test")
    await session.append("assistant", "response")

    ticker = MemoryTicker(llm, session_mgr, memory_dir=os.path.join(tmp_dir, "memory"))
    await ticker.notify_session_end(session)
    await asyncio.sleep(0.05)

    summary_path = os.path.join(tmp_dir, "memory", "summaries")
    files_before = os.listdir(summary_path)

    # Second call — should skip (fingerprint unchanged)
    await ticker.notify_session_end(session)
    await asyncio.sleep(0.05)

    files_after = os.listdir(summary_path)
    assert len(files_after) == len(files_before)


@pytest.mark.asyncio
async def test_facts_extractor(tmp_dir, llm):
    # Set up summary first
    session_mgr = SessionManager()
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "I like short answers")
    await session.append("assistant", "Ok")

    memory_dir = os.path.join(tmp_dir, "memory")
    ticker = MemoryTicker(llm, session_mgr, memory_dir=memory_dir)
    await ticker.notify_session_end(session)
    await asyncio.sleep(0.05)

    # Now extract facts
    db_path = os.path.join(tmp_dir, "test.db")
    db = Database(db_path)
    db.migrate()

    extractor = FactsExtractor(llm, db, memory_dir=memory_dir)
    count = await extractor.process_dirty()
    assert count >= 1

    # Verify fact in DB
    facts = db.execute("SELECT fact FROM facts_fts WHERE facts_fts MATCH 'short'")
    db.close()
    assert len(facts) >= 1


@pytest.mark.asyncio
async def test_daily_compiler(tmp_dir, llm):
    session_mgr = SessionManager()
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Test conversation")
    await session.append("assistant", "Test response")

    memory_dir = os.path.join(tmp_dir, "memory")
    ticker = MemoryTicker(llm, session_mgr, memory_dir=memory_dir)
    await ticker.notify_session_end(session)
    await asyncio.sleep(0.05)

    compiler = DailyCompiler(llm, memory_dir)
    await compiler.compile_all()

    assert os.path.exists(os.path.join(memory_dir, "today.md"))
    assert os.path.exists(os.path.join(memory_dir, "memory.md"))


@pytest.mark.asyncio
async def test_daily_compiler_no_summaries(tmp_dir, llm):
    """When no summaries exist, compile_all should return early without errors."""
    memory_dir = os.path.join(tmp_dir, "memory")
    os.makedirs(memory_dir, exist_ok=True)
    compiler = DailyCompiler(llm, memory_dir)
    await compiler.compile_all()
    assert not os.path.exists(os.path.join(memory_dir, "today.md"))


@pytest.mark.asyncio
async def test_daily_compiler_week_appends(tmp_dir, llm):
    """Week compilation appends today.md content to week.md."""
    session_mgr = SessionManager()
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Week test")
    await session.append("assistant", "Response")

    memory_dir = os.path.join(tmp_dir, "memory")
    ticker = MemoryTicker(llm, session_mgr, memory_dir=memory_dir)
    await ticker.notify_session_end(session)
    await asyncio.sleep(0.05)

    compiler = DailyCompiler(llm, memory_dir)
    await compiler.compile_all()
    assert os.path.exists(os.path.join(memory_dir, "week.md"))


@pytest.mark.asyncio
async def test_daily_compiler_memory_md_content(tmp_dir, llm):
    """memory.md should contain content from today.md."""
    session_mgr = SessionManager()
    session = await session_mgr.create(tmp_dir)
    await session.append("user", "Memory check")
    await session.append("assistant", "Ok")

    memory_dir = os.path.join(tmp_dir, "memory")
    ticker = MemoryTicker(llm, session_mgr, memory_dir=memory_dir)
    await ticker.notify_session_end(session)
    await asyncio.sleep(0.05)

    compiler = DailyCompiler(llm, memory_dir)
    await compiler.compile_all()

    with open(os.path.join(memory_dir, "memory.md")) as f:
        content = f.read()
    assert len(content) > 0


@pytest.mark.asyncio
async def test_load_memory_empty_dir():
    """When memory dir has no files, should return empty strings."""
    with tempfile.TemporaryDirectory() as d:
        from cococat.prompt import load_memory_from_agent_dir
        memory, pinned = load_memory_from_agent_dir(d)
        assert memory == ""
        assert pinned == ""


@pytest.mark.asyncio
async def test_load_memory_with_pinned():
    """pinned.md should be loaded separately from memory.md."""
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "memory"))
        with open(os.path.join(d, "memory", "memory.md"), "w") as f:
            f.write("memory content")
        with open(os.path.join(d, "pinned.md"), "w") as f:
            f.write("- pin1\n- pin2")
        from cococat.prompt import load_memory_from_agent_dir
        memory, pinned = load_memory_from_agent_dir(d)
        assert "memory content" in memory
        assert "pin1" in pinned
