"""Test sub_agent tool — dispatches task to SandboxProvider."""
import pytest
from cococat.core.tools import create_core_tools, ToolRegistry


class TestSubAgentTool:
    @pytest.mark.asyncio
    async def test_dispatches_task_and_returns_task_id(self):
        """When sub_agent tool is called, the dispatch function runs and returns a task_id."""
        dispatched = {}

        async def mock_executor(task: str, agent_id: str) -> str:
            dispatched["task"] = task
            dispatched["agent_id"] = agent_id
            return "abc123"

        tools = create_core_tools(sub_agent_executor=mock_executor)
        reg = ToolRegistry(tools)

        result = await reg.execute("sub_agent", {
            "task": "write a poem",
            "agent_id": "helper-1",
        })

        assert result == "abc123"
        assert dispatched["task"] == "write a poem"
        assert dispatched["agent_id"] == "helper-1"

    @pytest.mark.asyncio
    async def test_returns_stub_when_no_executor(self):
        """When no executor is configured, returns a stub message."""
        tools = create_core_tools()
        reg = ToolRegistry(tools)

        result = await reg.execute("sub_agent", {
            "task": "anything",
            "agent_id": "x",
        })

        assert "stub" in result.lower()
