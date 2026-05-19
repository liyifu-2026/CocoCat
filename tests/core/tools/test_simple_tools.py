"""Test simple tools: wait, current_status."""
import pytest


class TestWait:
    @pytest.mark.asyncio
    async def test_wait_returns_ok(self, registry):
        result = await registry.execute("wait", {"seconds": 0.01})
        assert "slept" in result.lower() or "waited" in result.lower() or "ok" in result.lower()

    @pytest.mark.asyncio
    async def test_wait_missing_seconds(self, registry):
        result = await registry.execute("wait", {})
        assert "0s" in result or "0" in result

    @pytest.mark.asyncio
    async def test_wait_zero(self, registry):
        result = await registry.execute("wait", {"seconds": 0})
        assert "slept" in result.lower() or "waited" in result.lower() or "ok" in result.lower()


class TestCurrentStatus:
    @pytest.mark.asyncio
    async def test_current_status_returns_string(self, registry):
        result = await registry.execute("current_status", {})
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_current_status_with_context(self, registry):
        ctx = {"agent_id": "test-agent", "bound_scene": "test-scene"}
        result = await registry.execute("current_status", {}, ctx)
        assert "test-agent" in result or "test-scene" in result
