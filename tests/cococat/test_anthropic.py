"""Tests for Anthropic provider."""
import pytest
from cococat.providers.anthropic import AnthropicProvider


@pytest.fixture
def provider():
    return AnthropicProvider(
        api_key="test-key",
        model="claude-sonnet-4-20250514",
    )


def test_anthropic_build_request_text_only(provider):
    system, messages = provider._convert_messages([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ])
    body = provider._build_request(messages, system=system)
    assert body["model"] == "claude-sonnet-4-20250514"
    assert body["system"] == "You are helpful."
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"][0]["type"] == "text"
    assert body["messages"][0]["content"][0]["text"] == "Hello"
    assert body["stream"] is False
    assert body["max_tokens"] == 4096


def test_anthropic_build_request_with_tools(provider):
    system, messages = provider._convert_messages([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Read the file"},
    ])
    body = provider._build_request(
        system=system, messages=messages,
        tools=[{
            "name": "read_file",
            "description": "Read a file",
            "parameters": {"path": {"type": "string"}},
        }],
    )
    assert len(body["tools"]) == 1
    assert body["tools"][0]["name"] == "read_file"
    assert body["tools"][0]["input_schema"]["type"] == "object"


def test_anthropic_convert_messages(provider):
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!", "tool_calls": [
            {"id": "tc1", "type": "function",
             "function": {"name": "read_file", "arguments": '{"path": "/tmp/x"}'}}
        ]},
        {"role": "tool", "tool_call_id": "tc1", "content": "file contents"},
        {"role": "user", "content": "Thanks"},
    ]

    system, converted = provider._convert_messages(messages)

    assert system == "You are helpful."
    assert len(converted) == 4  # user, assistant with tool_use, tool_result, user

    # Check tool_use conversion
    assistant_msg = converted[1]
    assert assistant_msg["role"] == "assistant"
    blocks = assistant_msg["content"]
    assert any(b["type"] == "tool_use" for b in blocks)

    # Check tool_result conversion
    tool_msg = converted[2]
    assert tool_msg["role"] == "user"
    assert tool_msg["content"][0]["type"] == "tool_result"
    assert tool_msg["content"][0]["tool_use_id"] == "tc1"
