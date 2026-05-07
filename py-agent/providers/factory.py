from __future__ import annotations

import os

from .base import LLMProvider
from .registry import find_by_model, find_by_env, ProviderSpec


def _get_env(spec: ProviderSpec) -> str:
    return os.environ.get(spec.env_key, "")


def _find_first_available() -> ProviderSpec | None:
    from .registry import PROVIDERS
    for spec in PROVIDERS:
        if _get_env(spec):
            return spec
    return None


def make_provider(model: str = "") -> LLMProvider:
    """Auto-detect and create the right LLM provider.

    Priority:
    1. Model name keyword match (e.g. 'deepseek-chat' -> deepseek)
    2. Env var detection (first provider whose env_key is set)
    3. Fallback: first provider with any available API key
    4. Ultimate fallback: first provider in registry
    """
    spec = find_by_model(model) if model else None
    if spec and spec.env_key and not _get_env(spec):
        spec = None
    if not spec:
        spec = find_by_env()
    if not spec:
        spec = _find_first_available()
    if not spec:
        from .registry import PROVIDERS
        spec = PROVIDERS[0]

    from provider_config import get_provider as _get_provider_cfg, get_api_key

    api_key = get_api_key(spec.name) or _get_env(spec) or os.environ.get("OPENAI_API_KEY", "")
    cfg = _get_provider_cfg(spec.name)
    base_url = cfg.get("api_base", "") or spec.default_api_base

    if spec.backend == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model, base_url=base_url)

    from .openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(api_key=api_key, model=model, base_url=base_url)


def ensure_model_catalog():
    """Fetch and cache model catalog on first use."""
    from provider_config import load_models, fetch_and_cache_models
    if not load_models():
        fetch_and_cache_models()
