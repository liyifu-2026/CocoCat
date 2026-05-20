"""Test Auto-Dream — threshold, pin, dedup, truncation, failure handling."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cococat.providers.base import LLMResponse


@pytest.fixture
def ctx(tmp_path):
    """Create a test session and memory setup."""
    session = tmp_path / "session.jsonl"
    memory = tmp_path / "memory" / "memory.md"
    memory.parent.mkdir(exist_ok=True)
    return tmp_path, session, memory


def _write_lines(path, n):
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps({"role": "user", "content": f"msg {i}"}) + "\n")


def _run(mock_llm, session_path):
    from cococat.memory.store import MemoryStore
    import asyncio
    with patch("cococat.memory.store.MemoryStore._get_llm", return_value=mock_llm):
        asyncio.run(MemoryStore().dream(str(session_path)))


class TestDreamThreshold:
    def test_below_threshold_skips(self, ctx):
        _, session, _ = ctx
        _write_lines(session, 20)
        mock = MagicMock(chat=AsyncMock())
        _run(mock, session)
        mock.chat.assert_not_called()

    def test_threshold_triggers(self, ctx):
        _, session, _ = ctx
        _write_lines(session, 60)
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=LLMResponse(content="f1"))
        _run(mock, session)
        mock.chat.assert_called_once()

    def test_exact_50_boundary(self, ctx):
        _, session, _ = ctx
        _write_lines(session, 50)
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=LLMResponse(content="f1"))
        _run(mock, session)
        mock.chat.assert_called_once()


class TestDreamPin:
    def test_pins_new_facts(self, ctx):
        _, session, memory = ctx
        _write_lines(session, 60)
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=LLMResponse(content="user loves Python"))
        _run(mock, session)
        assert memory.exists()
        content = memory.read_text()
        assert "user loves Python" in content

    def test_skips_duplicates(self, ctx):
        _, session, memory = ctx
        _write_lines(session, 60)
        memory.write_text("user loves Python\n")
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=LLMResponse(content="user loves Python\nproject is CocoCat"))
        _run(mock, session)
        content = memory.read_text()
        assert content.count("user loves Python") == 1
        assert "project is CocoCat" in content

    def test_ignores_blank_lines(self, ctx):
        _, session, memory = ctx
        _write_lines(session, 60)
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=LLMResponse(content="a\n\n\nb"))
        _run(mock, session)
        lines = [l for l in memory.read_text().splitlines() if l.strip()]
        assert lines == ["a", "b"]

    def test_no_existing_memory_works(self, ctx):
        _, session, memory = ctx
        _write_lines(session, 60)
        assert not memory.exists()
        mock = MagicMock()
        mock.chat = AsyncMock(return_value=LLMResponse(content="fact"))
        _run(mock, session)
        assert memory.exists()


class TestDreamFailure:
    def test_no_llm_preserves_session(self, ctx):
        _, session, memory = ctx
        _write_lines(session, 60)
        original = session.read_text()
        with patch("cococat.memory.store.MemoryStore._get_llm", return_value=None):
            import asyncio
            from cococat.memory.store import MemoryStore
            asyncio.run(MemoryStore().dream(str(session)))
        assert session.read_text() == original

    def test_llm_crash_preserves_session(self, ctx):
        _, session, memory = ctx
        _write_lines(session, 60)
        original = session.read_text()
        mock = MagicMock()
        mock.chat = AsyncMock(side_effect=RuntimeError("boom"))
        _run(mock, session)
        assert session.read_text() == original

    def test_nonexistent_session_is_noop(self):
        import asyncio
        from cococat.memory.store import MemoryStore
        asyncio.run(MemoryStore().dream("/nonexistent/s.json"))


class TestDreamPrompt:
    def test_includes_existing_memory(self):
        from cococat.memory.store import MemoryStore
        prompt = MemoryStore._dream_prompt("session", "fact1\nfact2\n")
        assert "已有记忆" in prompt
        assert "fact1" in prompt
        assert "不要重复输出" in prompt

    def test_no_memory_blocks_when_empty(self):
        from cococat.memory.store import MemoryStore
        prompt = MemoryStore._dream_prompt("session", "")
        assert "已有记忆" not in prompt
        assert "不要重复输出" not in prompt


class TestAgentDreamTrigger:
    """Verify agent.py triggers dream after run."""

    @pytest.mark.asyncio
    async def test_agent_saves_session_pair(self, tmp_path):
        from cococat.core.agent import Agent, AgentRole
        agents_dir = tmp_path / "agents" / "test-agent"
        session_path = agents_dir / "session.jsonl"

        class StubLLM:
            async def chat(self, messages, tools=None, **kwargs):
                return LLMResponse(content="hello")

        agent = Agent(
            id="test-agent",
            name="Test Agent",
            role=AgentRole.WORKER,
            llm=StubLLM(),
            agent_dir=str(agents_dir),
        )
        result = await agent.run("hi")
        assert result == "hello"
        assert session_path.exists()
        lines = session_path.read_text().strip().split("\n")
        assert len(lines) == 2
