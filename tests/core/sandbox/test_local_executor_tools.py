"""Tests for InProcessExecutor accepting custom tools from task dict."""
import pytest


CUSTOM_TOOLS = [{"name": "my_tool", "description": "A test tool", "parameters": {}, "execute": lambda p, ctx: "ok"}]


class TestInProcessExecutorTools:
    @pytest.mark.asyncio
    async def test_uses_custom_tools_from_task(self, monkeypatch):
        """When task has tools, InProcessExecutor should use them instead of full set."""
        from cococat.core.sandbox import InProcessExecutor, Sandbox

        captured_tools = []

        class FakeAgent:
            def __init__(self, id, name, role, llm, tools, agent_dir=None):
                captured_tools.append([t["name"] for t in tools])

            async def run(self, *args, **kwargs):
                return "done"

        monkeypatch.setattr("cococat.core.agent.Agent", FakeAgent)

        async def fake_llm(*a, **kw):
            return "done"

        executor = InProcessExecutor()
        executor._resolve_llm = lambda agent_id: fake_llm

        sandbox = Sandbox(id="test-1", template="default", permissions={})
        result = await executor.run(sandbox, "hello",
                                    agent_id="main", tools=CUSTOM_TOOLS)

        assert result == "done"
        assert captured_tools == [["my_tool"]]

    @pytest.mark.asyncio
    async def test_falls_back_to_default_tools_when_none_provided(self, monkeypatch):
        """When task has no tools, InProcessExecutor should use create_core_tools()."""
        from cococat.core.sandbox import InProcessExecutor, Sandbox

        captured_tools = []

        class FakeAgent:
            def __init__(self, id, name, role, llm, tools, agent_dir=None):
                captured_tools.append([t["name"] for t in tools])

            async def run(self, *args, **kw):
                return "done"

        monkeypatch.setattr("cococat.core.agent.Agent", FakeAgent)

        async def fake_llm(*a, **kw):
            return "done"

        executor = InProcessExecutor()
        executor._resolve_llm = lambda agent_id: fake_llm

        sandbox = Sandbox(id="test-2", template="default", permissions={})
        result = await executor.run(sandbox, "hello", agent_id="main")

        assert result == "done"
        names = captured_tools[0]
        assert "bash" in names
        assert "read_file" in names
        assert len(names) >= 20  # full toolset
