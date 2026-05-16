"""Tests for tool_executor — tool call dispatch and message building."""
import pytest
from cococat.core.tool_executor import execute_tool_calls, make_assistant_msg
from cococat.providers.base import ToolCallRequest


class TestMakeAssistantMsg:
    def test_builds_openai_format_from_dicts(self):
        tool_calls = [{
            "id": "call_1",
            "name": "web_search",
            "arguments": '{"query": "test"}',
        }]
        msg = make_assistant_msg("thinking...", tool_calls)

        assert msg["role"] == "assistant"
        assert msg["content"] == "thinking..."
        assert len(msg["tool_calls"]) == 1
        tc = msg["tool_calls"][0]
        assert tc["id"] == "call_1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "web_search"
        assert tc["function"]["arguments"] == '{"query": "test"}'

    def test_builds_openai_format_from_objects(self):
        tool_calls = [ToolCallRequest(id="call_2", name="bash", arguments='{"cmd": "ls"}')]
        msg = make_assistant_msg("", tool_calls)

        assert msg["tool_calls"][0]["function"]["name"] == "bash"

    def test_multiple_tool_calls(self):
        tool_calls = [
            {"id": "a", "name": "read_file", "arguments": '{"path": "x"}'},
            {"id": "b", "name": "bash", "arguments": '{"command": "ls"}'},
        ]
        msg = make_assistant_msg("ok", tool_calls)
        assert len(msg["tool_calls"]) == 2


class TestExecuteToolCalls:
    @pytest.mark.asyncio
    async def test_executes_matching_tool_and_appends_result(self):
        tools = [{
            "name": "echo",
            "description": "Echo",
            "parameters": {"text": "string"},
            "execute": lambda p, ctx: f"echo: {p.get('text', '')}",
        }]

        tool_calls = [{"id": "c1", "name": "echo", "arguments": '{"text": "hello"}'}]
        messages = []

        await execute_tool_calls(tool_calls, messages, tools, context={})

        assert len(messages) == 1
        assert messages[0]["role"] == "tool"
        assert messages[0]["tool_call_id"] == "c1"
        assert "echo: hello" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        tools = []
        tool_calls = [{"id": "c1", "name": "nonexistent", "arguments": "{}"}]
        messages = []

        await execute_tool_calls(tool_calls, messages, tools, context={})

        assert "Unknown tool" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_malformed_json_returns_error(self):
        tools = [{
            "name": "parse",
            "description": "Parse",
            "parameters": {},
            "execute": lambda p, ctx: "ok",
        }]
        tool_calls = [{"id": "c1", "name": "parse", "arguments": "{bad"}]
        messages = []

        await execute_tool_calls(tool_calls, messages, tools, context={})

        assert "error" in messages[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_executes_async_tool(self):
        async def async_tool(p, ctx):
            return "async result"

        tools = [{
            "name": "async_op",
            "description": "Async",
            "parameters": {},
            "execute": async_tool,
        }]
        tool_calls = [{"id": "c1", "name": "async_op", "arguments": "{}"}]
        messages = []

        await execute_tool_calls(tool_calls, messages, tools, context={})

        assert "async result" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_calls_on_tool_callback(self):
        tools = [{
            "name": "cb",
            "description": "CB",
            "parameters": {},
            "execute": lambda p, ctx: "done",
        }]
        tool_calls = [{"id": "c1", "name": "cb", "arguments": "{}"}]
        messages = []
        events = []

        async def on_tool(name, status, data):
            events.append((name, status))

        await execute_tool_calls(tool_calls, messages, tools, context={}, on_tool=on_tool)

        assert events == [("cb", "start"), ("cb", "done")]

    @pytest.mark.asyncio
    async def test_preserves_existing_messages(self):
        tools = [{
            "name": "add",
            "description": "Add",
            "parameters": {},
            "execute": lambda p, ctx: "42",
        }]
        tool_calls = [{"id": "c1", "name": "add", "arguments": "{}"}]
        messages = [{"role": "user", "content": "what is 6*7?"}]

        await execute_tool_calls(tool_calls, messages, tools, context={})

        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "tool"

    @pytest.mark.asyncio
    async def test_executing_tool_raises_exception_returns_error(self):
        def broken_tool(p, ctx):
            raise RuntimeError("boom")

        tools = [{
            "name": "broken",
            "description": "Broken",
            "parameters": {},
            "execute": broken_tool,
        }]
        tool_calls = [{"id": "c1", "name": "broken", "arguments": "{}"}]
        messages = []

        await execute_tool_calls(tool_calls, messages, tools, context={})

        assert "boom" in messages[0]["content"]
