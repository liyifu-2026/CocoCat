import pytest
import os
import sys
import json
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import LLMClient, LLMResponse, OpenAICompatibleProvider
from llm import _sanitize_openai_messages


class TestLLMClient:
    def test_empty_messages_returns_error(self):
        client = LLMClient(providers=[])
        result = client.chat([])
        assert "fail" in result.get("content", "").lower() or "error" in result.get("content", "").lower()

    def test_chat_with_no_providers(self):
        client = LLMClient(providers=[])
        result = client.chat([{"role": "user", "content": "hello"}])
        assert isinstance(result, dict)
        assert "fail" in result.get("content", "").lower() or "error" in result.get("content", "").lower()

    def test_retry_on_failure(self):
        mock_provider = Mock()
        mock_provider.chat.side_effect = Exception("API failure")
        client = LLMClient(providers=[mock_provider])
        result = client.chat([{"role": "user", "content": "hello"}])
        assert mock_provider.chat.call_count <= 4
        assert "error" in result.get("content", "").lower() or "fail" in result.get("content", "").lower()

    def test_success_on_second_attempt(self):
        mock_provider = Mock()
        mock_provider.chat.side_effect = [
            Exception("first failure"),
            LLMResponse(content="success"),
        ]
        client = LLMClient(providers=[mock_provider])
        result = client.chat([{"role": "user", "content": "hello"}])
        assert "success" in result.get("content", "")

    def test_provider_fallback_chain(self):
        failing = Mock()
        failing.chat.side_effect = Exception("provider 1 failed")
        succeeding = Mock()
        succeeding.chat.return_value = LLMResponse(content="provider 2 works")
        client = LLMClient(providers=[failing, succeeding])
        result = client.chat([{"role": "user", "content": "hello"}])
        assert "provider 2 works" in result.get("content", "")

    def test_auto_detect_returns_list(self):
        with patch.dict(os.environ, {}, clear=True):
            client = LLMClient()
            assert len(client.providers) > 0


class TestLLMResponse:
    def test_to_dict(self):
        response = LLMResponse(content="hello", tool_calls=[{"id": "1", "name": "test", "arguments": {}}])
        d = response.to_dict()
        assert d["content"] == "hello"
        assert len(d["tool_calls"]) == 1

    def test_default_values(self):
        response = LLMResponse()
        d = response.to_dict()
        assert d["content"] == ""
        assert d["tool_calls"] == []
        assert d["finish_reason"] == "stop"


class TestSanitizeMessages:
    def test_removes_extra_keys(self):
        messages = [
            {"role": "user", "content": "hello", "extra_key": "should_remove"},
            {"role": "assistant", "content": "hi", "tool_calls": []},
        ]
        sanitized = _sanitize_openai_messages(messages)
        assert "extra_key" not in sanitized[0]
        assert len(sanitized) == 2

    def test_allows_valid_keys(self):
        messages = [
            {"role": "user", "content": "hello", "tool_call_id": "123", "name": "test", "reasoning_content": "reasoning"},
        ]
        sanitized = _sanitize_openai_messages(messages)
        for key in ["role", "content", "tool_call_id", "name", "reasoning_content"]:
            assert key in sanitized[0]


class TestOpenAIProvider:
    def test_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAICompatibleProvider()
            assert provider.api_key == ""
