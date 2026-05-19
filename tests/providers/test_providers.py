"""Tests for cococat.providers."""
import os
import json
import tempfile
import pytest
from cococat.providers.base import BaseProvider, LLMResponse, ToolCallRequest
from cococat.providers.openai_compat import OpenAICompatProvider
from cococat.providers.credentials import CredentialManager
from cococat.providers.registry import ProviderRegistry, ProviderSpec, find_by_name, find_by_model, find_by_env, create_builtin_registry


# ── LLMResponse ──

def test_llm_response_defaults():
    resp = LLMResponse(content="hello")
    assert resp.content == "hello"
    assert resp.tool_calls == []
    assert resp.finish_reason == "stop"
    assert resp.usage == {}


def test_llm_response_with_tool_calls():
    tc = ToolCallRequest(id="call_1", name="read_file", arguments={"path": "/tmp/x"})
    resp = LLMResponse(content=None, tool_calls=[tc], finish_reason="tool_calls")
    assert resp.has_tool_calls is True
    assert resp.content is None
    assert resp.tool_calls[0].id == "call_1"
    assert resp.tool_calls[0].name == "read_file"
    assert resp.tool_calls[0].arguments == {"path": "/tmp/x"}


def test_llm_response_error():
    resp = LLMResponse(
        content="rate limit exceeded",
        finish_reason="error",
        error_status_code=429,
        error_type="rate_limit_error",
    )
    assert resp.finish_reason == "error"
    assert resp.error_status_code == 429
    assert resp.error_type == "rate_limit_error"


# ── Credential Manager ──

def test_credentials_load_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"deepseek": "sk-test123", "openai": "sk-openai456"}, f)
        path = f.name

    cm = CredentialManager(path)
    assert cm.get("deepseek") == "sk-test123"
    assert cm.get("openai") == "sk-openai456"
    assert cm.get("nonexistent") is None


def test_credentials_env_var_fallback():
    os.environ["TEST_PROVIDER_KEY"] = "env-key-789"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"test_provider": "${TEST_PROVIDER_KEY}"}, f)
        path = f.name

    cm = CredentialManager(path)
    assert cm.get("test_provider") == "env-key-789"
    del os.environ["TEST_PROVIDER_KEY"]


def test_credentials_file_not_found():
    cm = CredentialManager("/nonexistent/auth.json")
    assert cm.get("any") is None


# ── ProviderSpec ──

def test_provider_spec_fields():
    spec = ProviderSpec(
        name="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        backend="openai_compat",
        default_api_base="https://api.deepseek.com",
        supports_streaming=True,
    )
    assert spec.name == "deepseek"
    assert "deepseek" in spec.keywords
    assert spec.env_key == "DEEPSEEK_API_KEY"
    assert spec.display_name == "DeepSeek"


def test_builtin_registry_has_core_providers():
    reg = create_builtin_registry()
    assert reg.find_by_name("deepseek") is not None
    assert reg.find_by_name("openai") is not None
    assert reg.find_by_name("anthropic") is not None
    assert reg.find_by_name("ollama") is not None
    assert len(reg.list_all()) >= 14


def test_module_find_by_name():
    spec = find_by_name("deepseek")
    assert spec is not None
    assert spec.name == "deepseek"
    assert spec.display_name == "DeepSeek"


def test_module_find_by_name_nonexistent():
    assert find_by_name("nonexistent-provider-xyz") is None


def test_module_find_by_model_keyword():
    spec = find_by_model("deepseek-chat")
    assert spec is not None
    assert spec.name == "deepseek"

    spec2 = find_by_model("claude-sonnet-4-20250514")
    assert spec2 is not None
    assert spec2.name == "anthropic"

    spec3 = find_by_model("gpt-4o")
    assert spec3 is not None
    assert spec3.name == "openai"


def test_module_find_by_model_nonexistent():
    assert find_by_model("nonexistent-model-12345") is None


def test_module_find_by_env():
    os.environ["DEEPSEEK_API_KEY"] = "sk-test"
    spec = find_by_env()
    assert spec is not None
    assert spec.name == "deepseek"
    del os.environ["DEEPSEEK_API_KEY"]


def test_module_find_by_env_none_set():
    spec = find_by_env()
    assert spec is None


# ── Provider Registry ──

@pytest.fixture
def registry():
    reg = ProviderRegistry()
    reg.register(ProviderSpec(
        name="openai",
        keywords=("openai", "gpt"),
        env_key="OPENAI_API_KEY",
        display_name="OpenAI",
        default_api_base="https://api.openai.com/v1",
    ))
    reg.register(ProviderSpec(
        name="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        default_api_base="https://api.deepseek.com/v1",
    ))
    return reg


def test_registry_find_by_name(registry):
    p = registry.find_by_name("deepseek")
    assert p.display_name == "DeepSeek"


def test_registry_find_by_model(registry):
    p = registry.find_by_model("deepseek-chat")
    assert p.name == "deepseek"


def test_registry_list_all(registry):
    all_p = registry.list_all()
    assert len(all_p) == 2


# ── OpenAI Compat Provider ──

@pytest.mark.asyncio
async def test_openai_compat_chat_format():
    """Verify OpenAI-compat provider builds correct request format."""
    provider = OpenAICompatProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
    )
    request = provider._build_request(
        messages=[{"role": "user", "content": "Hello"}],
        tools=[{"name": "read_file", "description": "Read", "parameters": {}}],
    )
    assert request["model"] == "deepseek-chat"
    assert request["messages"][0]["role"] == "user"
    assert len(request["tools"]) == 1
    assert request["stream"] is False


@pytest.mark.asyncio
async def test_openai_compat_chat_returns_llm_response(monkeypatch):
    """chat() should return LLMResponse dataclass, not a bare dict."""
    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": "Hello from LLM",
                        "tool_calls": [{
                            "id": "call_1",
                            "function": {"name": "read_file", "arguments": '{"path": "/tmp/x"}'},
                        }],
                    },
                    "finish_reason": "tool_calls",
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def post(self, url, **kwargs): return FakeResponse()
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass

    import cococat.providers.openai_compat as mod
    monkeypatch.setattr(mod.httpx, "AsyncClient", FakeClient)

    provider = mod.OpenAICompatProvider(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    )
    result = await provider.chat([{"role": "user", "content": "Hi"}])
    assert isinstance(result, LLMResponse)
    assert result.content == "Hello from LLM"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "read_file"
    assert result.tool_calls[0].arguments == '{"path": "/tmp/x"}'
    assert result.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_openai_compat_chat_stream_yields_events(monkeypatch):
    """chat_stream() should yield typed delta events."""
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
        'data: {"choices":[{"delta":{"content":" world"}}]}\n',
        'data: [DONE]\n',
    ]

    class FakeStreamResponse:
        status_code = 200
        def raise_for_status(self): pass
        async def aiter_lines(self):
            for line in sse_lines: yield line
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass

    class FakeClient:
        def __init__(self, **kwargs): pass
        def stream(self, method, url, **kwargs): return FakeStreamResponse()
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass

    import cococat.providers.openai_compat as mod
    monkeypatch.setattr(mod.httpx, "AsyncClient", FakeClient)

    provider = mod.OpenAICompatProvider(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    )
    events = []
    async for event in provider.chat_stream([{"role": "user", "content": "Hi"}]):
        events.append(event)

    assert len(events) >= 2
    assert events[0]["type"] == "delta"


# ── Provider Factory ──

@pytest.mark.asyncio
async def test_factory_create_with_model():
    from cococat.providers.factory import ProviderFactory
    from cococat.providers.registry import ProviderRegistry
    from cococat.providers.credentials import CredentialManager

    creds = CredentialManager()
    reg = ProviderRegistry()
    reg.register(ProviderSpec(
        name="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        default_api_base="https://api.deepseek.com/v1",
    ))

    # Set key in env so factory finds it
    os.environ["DEEPSEEK_API_KEY"] = "sk-test"
    factory = ProviderFactory(credential_manager=creds, registry=reg)
    provider = await factory.create("deepseek-chat")
    assert provider is not None
    assert provider.model == "deepseek-chat"
    del os.environ["DEEPSEEK_API_KEY"]


@pytest.mark.asyncio
async def test_factory_create_no_provider_found():
    from cococat.providers.factory import ProviderFactory
    from cococat.providers.registry import ProviderRegistry

    reg = ProviderRegistry()
    factory = ProviderFactory(registry=reg)
    provider = await factory.create("unknown-model")
    assert provider is None


@pytest.mark.asyncio
async def test_factory_create_no_api_key():
    from cococat.providers.factory import ProviderFactory
    from cococat.providers.registry import ProviderRegistry
    from cococat.providers.credentials import CredentialManager

    reg = ProviderRegistry()
    reg.register(ProviderSpec(
        name="deepseek",
        keywords=("deepseek",),
        env_key="DEEPSEEK_API_KEY",
        display_name="DeepSeek",
        default_api_base="https://api.deepseek.com/v1",
    ))
    # Use a temp auth.json with empty content
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{}")
        path = f.name
    creds = CredentialManager(path)
    factory = ProviderFactory(credential_manager=creds, registry=reg)
    provider = await factory.create("deepseek-chat")
    assert provider is None  # No API key configured


def test_factory_create_sync_fallback():
    from cococat.providers.factory import ProviderFactory
    from cococat.providers.registry import ProviderRegistry
    from cococat.providers.credentials import CredentialManager

    # create_sync returns None outside of async context
    reg = ProviderRegistry()
    factory = ProviderFactory(registry=reg)
    provider = factory.create_sync("deepseek-chat")
    assert provider is None  # Not in async event loop


def test_registry_find_by_model_no_match(registry):
    p = registry.find_by_model("nonexistent-model-xyz")
    assert p is None


def test_credentials_nonexistent_provider():
    cm = CredentialManager()
    assert cm.get("nonexistent") is None
