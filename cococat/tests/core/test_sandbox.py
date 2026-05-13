"""Test SandboxProvider."""
import pytest
from cococat.core.sandbox import SandboxProvider, LocalExecutor


class TestSandboxProvider:
    @pytest.mark.asyncio
    async def test_create_and_destroy(self):
        provider = SandboxProvider()
        sid = await provider.create("default", {"kbs": ["test"]})
        assert sid.startswith("local-")
        await provider.destroy(sid)
        assert sid not in provider._sandboxes

    @pytest.mark.asyncio
    async def test_run_once_returns_string(self):
        provider = SandboxProvider()
        result = await provider.run_once("say hello", agent_id="main")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_once_with_events(self):
        events = []
        provider = SandboxProvider()
        result = await provider.run_once(
            "say hello",
            agent_id="main",
            on_event=lambda t, d: events.append((t, d)),
        )
        assert isinstance(result, str)
        # Events may or may not fire depending on LLM provider
        # Just verify the function doesn't crash

    @pytest.mark.asyncio
    async def test_run_unknown_sandbox(self):
        provider = SandboxProvider()
        with pytest.raises(ValueError, match="Unknown sandbox"):
            await provider.run("nonexistent", {"prompt": "hi"})

    @pytest.mark.asyncio
    async def test_concurrent_sandboxes(self):
        provider = SandboxProvider(executor=LocalExecutor(max_workers=2))
        s1 = await provider.create()
        s2 = await provider.create()
        assert s1 != s2
        await provider.destroy(s1)
        await provider.destroy(s2)
