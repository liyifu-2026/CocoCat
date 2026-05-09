"""Tests for cococat.providers."""
import os
import json
import tempfile
import pytest
from cococat.providers.base import BaseProvider
from cococat.providers.openai_compat import OpenAICompatProvider
from cococat.providers.credentials import CredentialManager
from cococat.providers.registry import ProviderRegistry


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


# ── Provider Registry ──

@pytest.fixture
def registry():
    reg = ProviderRegistry()
    reg.register("openai", {
        "name": "openai",
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "keywords": ["openai", "gpt"],
    })
    reg.register("deepseek", {
        "name": "deepseek",
        "display_name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "keywords": ["deepseek"],
    })
    return reg


def test_registry_find_by_name(registry):
    p = registry.find_by_name("deepseek")
    assert p["display_name"] == "DeepSeek"


def test_registry_find_by_model(registry):
    p = registry.find_by_model("deepseek-chat")
    assert p["name"] == "deepseek"


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


# ── Provider Factory ──

@pytest.mark.asyncio
async def test_factory_create_with_model():
    from cococat.providers.factory import ProviderFactory
    from cococat.providers.registry import ProviderRegistry
    from cococat.providers.credentials import CredentialManager

    creds = CredentialManager()
    reg = ProviderRegistry()
    reg.register("deepseek", {
        "name": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "keywords": ["deepseek"],
    })

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
    reg.register("deepseek", {
        "name": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "keywords": ["deepseek"],
    })
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
