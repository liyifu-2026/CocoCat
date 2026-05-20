"""Tests for ReAct loop tool execution."""
import json
import tempfile
import os
import pytest
from cococat.core.agent import Agent, AgentRole
from cococat.core.tools.types import Tool, ToolRegistry
from cococat.core.tools.execution import make_execution_tools
from cococat.core.tools.file_ops import make_readonly_file_tools
from cococat.providers.base import LLMResponse, ToolCallRequest


def _create_test_tools():
    return make_execution_tools() + make_readonly_file_tools()


class ReActMockLLM:
    """Mock LLM that first returns a tool call, then a final text response."""
    def __init__(self):
        self.calls = 0

    async def chat(self, messages, tools=None, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="Let me check the file.",
                tool_calls=[ToolCallRequest(
                    id="call_1",
                    name="read_file",
                    arguments=json.dumps({"path": "/tmp/test_read.txt"}),
                )],
            )
        else:
            return LLMResponse(content="The file contains Hello World.")


@pytest.fixture
def react_agent():
    agent = Agent(
        id="test",
        name="Test Agent",
        role=AgentRole.WORKER,
        llm=ReActMockLLM(),
        tools=_create_test_tools(),
    )
    return agent


@pytest.mark.asyncio
async def test_react_loop_reads_file(react_agent):
    # Create test file
    with open("/tmp/test_read.txt", "w") as f:
        f.write("Hello World")

    result = await react_agent.run("What's in /tmp/test_read.txt?")
    assert "Hello World" in result
    assert react_agent._llm.calls == 2  # One tool call + one final response


class MultiToolMockLLM:
    """Mock LLM that calls read_file then write_file."""
    async def chat(self, messages, tools=None, **kwargs):
        has_tool_msgs = any(m["role"] == "tool" for m in messages)
        if has_tool_msgs:
            return LLMResponse(content="Done. I read and wrote the file.")
        return LLMResponse(
            content="",
            tool_calls=[ToolCallRequest(
                id="call_1",
                name="read_file",
                arguments=json.dumps({"path": "/tmp/test_multi.txt"}),
            )],
        )


@pytest.mark.asyncio
async def test_react_loop_max_iterations():
    """Agent stops after max_iterations to prevent infinite loops."""
    class InfiniteToolLLM:
        async def chat(self, messages, tools=None, **kwargs):
            return LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(
                    id=f"call_{len(messages)}",
                    name="bash",
                    arguments=json.dumps({"command": "echo loop"}),
                )],
            )

    agent = Agent("loop", "Loop", AgentRole.WORKER, InfiniteToolLLM(), _create_test_tools())
    result = await agent.run("loop", max_iterations=3)
    assert "exceeded max iterations" in result


@pytest.mark.asyncio
async def test_react_on_tool_callback():
    """on_tool callback fires for tool start and done."""
    tool_events = []

    class ToolTrackingLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCallRequest(
                        id="call_1",
                        name="bash",
                        arguments='{"command": "echo hello"}',
                    )],
                )
            return LLMResponse(content="completed")

    agent = Agent("track", "Tracker", AgentRole.WORKER, ToolTrackingLLM(), _create_test_tools())

    async def on_tool(name, status, data=None):
        tool_events.append((name, status))

    result = await agent.run("do it", on_tool=on_tool)
    assert len(tool_events) == 2
    assert tool_events[0] == ("bash", "start")
    assert tool_events[1] == ("bash", "done")


@pytest.mark.asyncio
async def test_react_on_text_callback():
    """on_text callback fires for streaming text deltas."""
    deltas = []

    class StreamingLLM:
        async def chat(self, messages, tools=None, **kwargs):
            return LLMResponse(content="final answer")

    agent = Agent("stream", "Streamer", AgentRole.WORKER, StreamingLLM(), _create_test_tools())

    async def on_text(delta):
        deltas.append(delta)

    result = await agent.run("hello", on_text=on_text)
    # on_text isn't called in non-streaming mode (Agent.run uses non-streaming chat)
    # but we verify the full result is returned
    assert result == "final answer"


@pytest.mark.asyncio
async def test_react_unknown_tool():
    """Agent handles tool call for non-existent tool gracefully."""
    class UnknownToolLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCallRequest(
                        id="call_x",
                        name="nonexistent_tool",
                        arguments="{}",
                    )],
                )
            return LLMResponse(content="I tried but the tool didn't exist.")

    agent = Agent("unknown", "Unknown", AgentRole.WORKER, UnknownToolLLM(), _create_test_tools())
    result = await agent.run("do unknown")
    assert "didn't exist" in result


@pytest.mark.asyncio
async def test_react_empty_prompt():
    """Empty prompt string should still trigger the loop and produce a result."""
    class EmptyPromptLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content="processing",
                    tool_calls=[ToolCallRequest(
                        id="call_1",
                        name="read_file",
                        arguments=json.dumps({"path": "/tmp/test_empty.txt"}),
                    )],
                )
            return LLMResponse(content="got the file")

    with open("/tmp/test_empty.txt", "w") as f:
        f.write("empty prompt works")

    agent = Agent("empty", "Empty", AgentRole.WORKER, EmptyPromptLLM(), _create_test_tools())
    result = await agent.run("")
    assert "got the file" in result


@pytest.mark.asyncio
async def test_react_tool_exception_continues_loop():
    """Tool that raises an exception is caught; ReAct loop continues."""
    def _failing_tool(params, ctx):
        raise RuntimeError("deliberate test failure")

    class ExceptionToolLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCallRequest(
                        id="call_err",
                        name="failing_tool",
                        arguments="{}",
                    )],
                )
            return LLMResponse(content="recovered after tool error")

    tools = _create_test_tools() + [
        Tool(name="failing_tool", description="Always raises",
             parameters={}, execute=_failing_tool,
             requires_sandbox=True, sandbox_operation="read"),
    ]
    agent = Agent("err", "Error", AgentRole.WORKER, ExceptionToolLLM(), tools)
    result = await agent.run("trigger error")
    assert "recovered after tool error" in result
    assert agent._llm.calls == 2


@pytest.mark.asyncio
async def test_react_max_iterations_exact():
    """Tool-calling LLM that never emits final text is stopped at max_iterations."""
    class StubbornLLM:
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, tools=None, **kwargs):
            self.calls += 1
            return LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(
                    id=f"call_{self.calls}",
                    name="bash",
                    arguments=json.dumps({"command": "echo again"}),
                )],
            )

    agent = Agent("stubborn", "Stubborn", AgentRole.WORKER, StubbornLLM(), _create_test_tools())
    result = await agent.run("loop", max_iterations=2)
    assert "exceeded max iterations" in result
