"""Provider configuration management — JSON-based config files with env var resolution."""
from __future__ import annotations

import json
import os
import re
import logging
from pathlib import Path

logger = logging.getLogger("cococat.provider_config")

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
PROVIDERS_PATH = CONFIG_DIR / "providers.json"
AUTH_PATH = CONFIG_DIR / "auth.json"
MODELS_PATH = CONFIG_DIR / "models.json"
AGENT_MODELS_PATH = CONFIG_DIR / "agent_models.json"

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve(value: str) -> str:
    """Resolve ${VAR} references in a string using environment variables."""
    def _replace(m: re.Match) -> str:
        return os.environ.get(m.group(1), "")
    return _ENV_VAR_RE.sub(_replace, value)


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: dict | list = None) -> dict | list:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read {path}: {e}")
        return default if default is not None else {}


def _write_json(path: Path, data: dict | list):
    _ensure_config_dir()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


# ── Provider config ───────────────────────────────────────────────────

def load_providers() -> dict:
    """Load provider configs. Returns {provider_name: {api_base, default_model, ...}}.
    
    API keys are stored as ${ENV_VAR} references and resolved at read time.
    """
    return _read_json(PROVIDERS_PATH, {})


def save_providers(data: dict):
    """Save provider configs. Keys stored as ${ENV_VAR} references if using env vars."""
    _write_json(PROVIDERS_PATH, data)


def get_provider(name: str) -> dict:
    return load_providers().get(name, {})


def update_provider(name: str, config: dict):
    providers = load_providers()
    providers[name] = config
    save_providers(providers)


# ── Auth storage ──────────────────────────────────────────────────────

def load_auth() -> dict:
    """Load stored API keys. Returns {provider_name: api_key_string}."""
    return _read_json(AUTH_PATH, {})


def save_auth(data: dict):
    """Save API keys. File is chmod 600."""
    _write_json(AUTH_PATH, data)


def get_api_key(provider_name: str) -> str:
    """Get API key for a provider. Checks: auth.json → env var → empty."""
    auth = load_auth()
    key = auth.get(provider_name, "")
    if key:
        return _resolve(key)

    from providers.registry import PROVIDERS
    for spec in PROVIDERS:
        if spec.name == provider_name:
            return os.environ.get(spec.env_key, "")
    return ""


def set_api_key(provider_name: str, key: str):
    """Store an API key for a provider."""
    auth = load_auth()
    auth[provider_name] = key
    save_auth(auth)


# ── Model catalog ─────────────────────────────────────────────────────

MODEL_CATALOG_URL = "https://models.dev"


def load_models() -> dict:
    """Load cached model catalog. Returns {provider_name: {models: [...], ...}}."""
    return _read_json(MODELS_PATH, {})


def save_models(data: dict):
    _write_json(MODELS_PATH, data)


def fetch_and_cache_models() -> bool:
    """Fetch model catalog from models.dev and cache locally. Returns True on success."""
    import urllib.request
    try:
        with urllib.request.urlopen(MODEL_CATALOG_URL, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        save_models(data)
        logger.info(f"Model catalog cached: {len(data)} providers")
        return True
    except Exception as e:
        logger.warning(f"Failed to fetch model catalog: {e}")
        return False


def get_available_models(provider_name: str = "") -> list[dict]:
    """Get available models for a provider from the catalog. Returns [{id, name, ...}, ...]."""
    catalog = load_models()
    if provider_name:
        return catalog.get(provider_name, {}).get("models", [])
    all_models = []
    for pname, pdata in catalog.items():
        for m in pdata.get("models", []):
            m["provider"] = pname
            all_models.append(m)
    return all_models


# ── Agent model assignments ───────────────────────────────────────────

def load_agent_models() -> dict:
    """Load per-agent model assignments. Returns {agent_id: {provider, model, reasoning_effort}}."""
    return _read_json(AGENT_MODELS_PATH, {})


def save_agent_models(data: dict):
    _write_json(AGENT_MODELS_PATH, data)


def get_agent_model(agent_id: str) -> dict:
    return load_agent_models().get(agent_id, {})


def set_agent_model(agent_id: str, provider: str, model: str, reasoning_effort: str = ""):
    models = load_agent_models()
    models[agent_id] = {
        "provider": provider,
        "model": model,
        "reasoning_effort": reasoning_effort,
    }
    save_agent_models(models)
