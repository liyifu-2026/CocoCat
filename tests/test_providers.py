import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

import pytest
from providers.base import LLMResponse, ToolCallRequest, LLMProvider
from providers.registry import find_by_name, find_by_model, PROVIDERS


class TestRegistry:
    def test_find_by_name(self):
        spec = find_by_name("deepseek")
        assert spec is not None
        assert spec.name == "deepseek"

    def test_find_by_name_nonexistent(self):
        assert find_by_name("nonexistent") is None

    def test_find_by_model(self):
        spec = find_by_model("deepseek-chat")
        assert spec is not None
        assert spec.name == "deepseek"

    def test_find_by_model_anthropic(self):
        spec = find_by_model("claude-sonnet-4")
        assert spec is not None
        assert spec.name == "anthropic"

    def test_find_by_model_gpt(self):
        spec = find_by_model("gpt-4o")
        assert spec is not None
        assert spec.name == "openai"

    def test_find_by_model_no_match(self):
        assert find_by_model("xyz-unknown-model-999") is None

    def test_all_providers_have_env_key_and_base(self):
        for spec in PROVIDERS:
            assert spec.env_key, f"{spec.name} missing env_key"
            assert spec.default_api_base, f"{spec.name} missing default_api_base"


class TestLLMResponse:
    def test_no_tool_calls(self):
        r = LLMResponse(content="hello")
        assert not r.has_tool_calls

    def test_has_tool_calls(self):
        r = LLMResponse(content="", tool_calls=[ToolCallRequest(id="1", name="test", arguments={})])
        assert r.has_tool_calls

    def test_should_execute_tools(self):
        r = LLMResponse(content="", tool_calls=[ToolCallRequest(id="1", name="test", arguments={})], finish_reason="tool_calls")
        assert r.should_execute_tools

    def test_should_not_execute_tools_on_error(self):
        r = LLMResponse(content="error", finish_reason="error")
        assert not r.should_execute_tools

    def test_should_not_execute_tools_no_tool_calls(self):
        r = LLMResponse(content="hello", finish_reason="stop")
        assert not r.should_execute_tools


class TestTransientDetection:
    def test_429_is_transient(self):
        r = LLMResponse(content="", finish_reason="error", error_status_code=429, error_type="rate_limit_error")
        assert LLMProvider._is_transient(r)

    def test_quota_is_not_transient(self):
        r = LLMResponse(content="", finish_reason="error", error_status_code=429, error_type="insufficient_quota")
        assert not LLMProvider._is_transient(r)

    def test_500_is_transient(self):
        r = LLMResponse(content="server error", finish_reason="error", error_status_code=500)
        assert LLMProvider._is_transient(r)

    def test_timeout_text_is_transient(self):
        r = LLMResponse(content="upstream timeout error", finish_reason="error", error_type="timeout")
        assert LLMProvider._is_transient(r)

    def test_connection_error_is_transient(self):
        r = LLMResponse(content="connection refused", finish_reason="error", error_type="connection")
        assert LLMProvider._is_transient(r)

    def test_billing_error_not_transient(self):
        r = LLMResponse(content="billing_hard_limit_reached", finish_reason="error", error_status_code=429)
        assert not LLMProvider._is_transient(r)

    def test_error_should_retry_overrides(self):
        r = LLMResponse(content="anything", finish_reason="error", error_should_retry=False)
        assert not LLMProvider._is_transient(r)

    def test_non_error_is_not_transient(self):
        r = LLMResponse(content="hello", finish_reason="stop")
        assert not LLMProvider._is_transient(r)


class TestRetryAfter:
    def test_extract_seconds(self):
        val = LLMProvider._extract_retry_after("retry after 5 seconds")
        assert val is not None and 4.9 <= val <= 5.1

    def test_extract_variant(self):
        val = LLMProvider._extract_retry_after('"retry_after": 10')
        assert val is not None and 9.9 <= val <= 10.1

    def test_extract_try_again(self):
        val = LLMProvider._extract_retry_after("try again in 30 seconds")
        assert val is not None and 29.9 <= val <= 30.1

    def test_no_match(self):
        assert LLMProvider._extract_retry_after("hello world") is None

    def test_empty_string(self):
        assert LLMProvider._extract_retry_after("") is None

    def test_none_input(self):
        assert LLMProvider._extract_retry_after(None) is None


class _ConcreteProvider(LLMProvider):
    def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
        return LLMResponse(content="hello")


class TestChatStream:
    def test_default_stream_fallback(self):
        results = list(_ConcreteProvider().chat_stream([{"role": "user", "content": "hi"}]))
        assert len(results) >= 2
        assert results[0]["type"] == "delta"
        assert results[-1]["type"] == "done"
