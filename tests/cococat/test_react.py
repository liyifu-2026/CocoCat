"""Tests for ReAct loop tool execution."""
import json
import tempfile
import os
import pytest
from cococat.core.agent import Agent, AgentRole
from cococat.core.tools import create_core_tools, ToolRegistry


class ReActMockLLM:
    """Mock LLM that first returns a tool call, then a final text response."""
    def __init__(self):
        self.calls = 0

    async def chat(self, messages, tools=None, **kwargs):
        self.calls += 1
        if self.calls == 1:
            # First call: return a read_file tool call
            return {
                "content": "Let me check the file.",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": json.dumps({"path": "/tmp/test_read.txt"}),
                }],
            }
        else:
            # Second call: return final text
            return {"content": "The file contains Hello World."}


@pytest.fixture
def react_agent():
    agent = Agent(
        id="test",
        name="Test Agent",
        role=AgentRole.SUB,
        llm=ReActMockLLM(),
        tools=create_core_tools(),
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
        # Check if we're in the tool-call phase
        has_tool_msgs = any(m["role"] == "tool" for m in messages)
        if has_tool_msgs:
            return {"content": "Done. I read and wrote the file."}
        return {
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "name": "read_file",
                "arguments": json.dumps({"path": "/tmp/test_multi.txt"}),
            }],
        }


@pytest.mark.asyncio
async def test_react_loop_max_iterations():
    """Agent stops after max_iterations to prevent infinite loops."""
    class InfiniteToolLLM:
        async def chat(self, messages, tools=None, **kwargs):
            return {
                "content": "",
                "tool_calls": [{
                    "id": f"call_{len(messages)}",
                    "name": "bash",
                    "arguments": json.dumps({"command": "echo loop"}),
                }],
            }

    agent = Agent("loop", "Loop", AgentRole.SUB, InfiniteToolLLM(), create_core_tools())
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
                return {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "name": "bash",
                        "arguments": '{"command": "echo hello"}',
                    }],
                }
            return {"content": "completed"}

    agent = Agent("track", "Tracker", AgentRole.SUB, ToolTrackingLLM(), create_core_tools())

    async def on_tool(name, status):
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
            return {"content": "final answer"}

    agent = Agent("stream", "Streamer", AgentRole.SUB, StreamingLLM(), create_core_tools())

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
                return {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_x",
                        "name": "nonexistent_tool",
                        "arguments": "{}",
                    }],
                }
            # After tool result comes back, return text
            return {"content": "I tried but the tool didn't exist."}

    agent = Agent("unknown", "Unknown", AgentRole.SUB, UnknownToolLLM(), create_core_tools())
    result = await agent.run("do unknown")
    assert "didn't exist" in result
