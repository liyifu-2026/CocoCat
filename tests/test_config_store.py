import json
import os
import yaml
import pytest
from pathlib import Path

from cococat.config_store import ConfigStore


@pytest.fixture
def store(tmp_path):
    return ConfigStore(config_dir=str(tmp_path / "config"))


# ── auth ──────────────────────────────────────────────────────

def test_auth_roundtrip(store):
    store.set_auth("openai", "sk-abc123")
    assert store.get_auth("openai") == "sk-abc123"
    assert store.get_auth("nonexistent") is None


def test_all_auth_returns_full_dict(store):
    store.set_auth("openai", "sk-abc")
    store.set_auth("anthropic", "sk-xyz")
    auth = store.all_auth()
    assert auth == {"openai": "sk-abc", "anthropic": "sk-xyz"}


def test_auth_cache_hit(store):
    store.set_auth("openai", "sk-abc")
    auth_path = store.auth_path
    auth_path.write_text('{"openai": "sk-overwritten"}')
    assert store.get_auth("openai") == "sk-abc"


def test_auth_env_override(tmp_path):
    alt_path = tmp_path / "alt" / "auth.json"
    alt_path.parent.mkdir(parents=True, exist_ok=True)
    alt_path.write_text('{"openai": "sk-from-env"}')
    os.environ["COCOCAT_AUTH_FILE"] = str(alt_path)
    try:
        s = ConfigStore(config_dir=str(tmp_path / "config"))
        assert s.auth_path == alt_path
        assert s.get_auth("openai") == "sk-from-env"
    finally:
        del os.environ["COCOCAT_AUTH_FILE"]


# ── defaults ──────────────────────────────────────────────────

def test_save_and_get_defaults(store):
    store.save_defaults({"theme": "dark", "language": "en"})
    assert store.get_default("theme") == "dark"
    assert store.get_default() == {"theme": "dark", "language": "en"}


def test_get_default_nonexistent_key(store):
    store.save_defaults({})
    assert store.get_default("missing") is None


# ── channels ──────────────────────────────────────────────────

def test_get_channel_configs_returns_empty_before_save(store):
    assert store.get_channel_configs() == {}


def test_channels_roundtrip(store):
    data = {"channels": {"discord": {"enabled": True}, "slack": {"enabled": False}}}
    store.save_channel_configs(data)
    result = store.get_channel_configs()
    assert result == data
    assert store.main_yaml_path.suffix == ".yaml"


# ── models ────────────────────────────────────────────────────

def test_models_roundtrip(store):
    data = {"openai": {"gpt-4o": {"context": 128000}}}
    store.save_models(data)
    assert store.get_models() == data


# ── custom providers ──────────────────────────────────────────

def test_custom_providers_roundtrip(store):
    data = [{"name": "my_provider", "base_url": "http://localhost"}]
    store.save_custom_providers(data)
    assert store.get_custom_providers() == data


def test_get_custom_providers_defaults_to_empty_list(store):
    assert store.get_custom_providers() == []


# ── residents ─────────────────────────────────────────────────

def test_get_resident_configs_from_yaml(store):
    residents_dir = store.residents_dir
    residents_dir.mkdir(parents=True, exist_ok=True)
    (residents_dir / "agent_a.yaml").write_text(
        yaml.safe_dump({"id": "agent_a", "name": "Alice"})
    )
    (residents_dir / "agent_b.yml").write_text(
        yaml.safe_dump({"id": "agent_b", "name": "Bob"})
    )
    configs = store.get_resident_configs()
    assert configs == {
        "agent_a": {"id": "agent_a", "name": "Alice"},
        "agent_b": {"id": "agent_b", "name": "Bob"},
    }


def test_resident_save_roundtrip(store):
    config = {"id": "agent_x", "role": "assistant"}
    store.save_resident_config("agent_x", config)
    configs = store.get_resident_configs()
    assert configs == {"agent_x": config}
    assert (store.residents_dir / "agent_x.yaml").is_file()


# ── coco prompt ───────────────────────────────────────────────

def test_get_coco_prompt_returns_none_when_no_file(store):
    assert store.get_coco_prompt() is None


def test_coco_prompt_roundtrip(store):
    store.save_coco_prompt("You are a helpful assistant.")
    assert store.get_coco_prompt() == "You are a helpful assistant."
    assert (store.prompts_dir / "coco.txt").read_text() == "You are a helpful assistant."


def test_delete_coco_prompt(store):
    store.save_coco_prompt("test prompt")
    assert store.delete_coco_prompt() is True
    assert store.get_coco_prompt() is None


def test_delete_coco_prompt_when_no_file(store):
    assert store.delete_coco_prompt() is False


# ── env ───────────────────────────────────────────────────────

def test_get_env_reads_os_environ(store):
    os.environ["COCOCAT_TEST_KEY"] = "test_value"
    try:
        assert store.get_env("COCOCAT_TEST_KEY") == "test_value"
        assert store.get_env("NONEXISTENT") is None
        assert store.get_env("NONEXISTENT", "fallback") == "fallback"
    finally:
        del os.environ["COCOCAT_TEST_KEY"]


def test_set_env_writes_to_dotenv(store):
    store.set_env("MY_VAR", "hello")
    assert os.environ["MY_VAR"] == "hello"
    content = Path(store._env_file_path()).read_text()
    assert "MY_VAR=hello" in content
    assert store.env_keys().get("MY_VAR") == "hello"


# ── cache invalidation ────────────────────────────────────────

def test_invalidate_clears_all_caches(store):
    store.save_defaults({"theme": "dark"})
    store.set_auth("openai", "sk-abc")
    assert store.get_default("theme") == "dark"
    assert store.get_auth("openai") == "sk-abc"

    defaults_path = store.defaults_path
    defaults_path.write_text('{"theme": "light"}')
    auth_path = store.auth_path
    auth_path.write_text('{"openai": "sk-overwritten"}')

    assert store.get_default("theme") == "dark"  # still cached
    assert store.get_auth("openai") == "sk-abc"  # still cached

    store.invalidate()

    assert store.get_default("theme") == "light"
    assert store.get_auth("openai") == "sk-overwritten"


# ── path overrides ────────────────────────────────────────────

def test_models_file_env_override(tmp_path):
    alt_path = tmp_path / "alt_models.json"
    alt_path.parent.mkdir(parents=True, exist_ok=True)
    alt_path.write_text('{"custom_model": {"size": "small"}}')
    os.environ["COCOCAT_MODELS_FILE"] = str(alt_path)
    try:
        s = ConfigStore(config_dir=str(tmp_path / "config"))
        assert s.models_path == alt_path
        assert s.get_models() == {"custom_model": {"size": "small"}}
    finally:
        del os.environ["COCOCAT_MODELS_FILE"]


def test_env_file_override(tmp_path):
    alt_env = tmp_path / "custom.env"
    alt_env.write_text("CUSTOM_VAR=from_custom_env\n")
    os.environ["COCOCAT_ENV_FILE"] = str(alt_env)
    try:
        s = ConfigStore(config_dir=str(tmp_path / "config"))
        assert s._env_file_path() == alt_env
        keys = s.env_keys()
        assert keys.get("CUSTOM_VAR") == "from_custom_env"
    finally:
        del os.environ["COCOCAT_ENV_FILE"]
