"""Provider factory — creates LLM providers from config."""

from __future__ import annotations

import logging
import os

from cococat.providers.base import BaseProvider
from cococat.providers.openai_compat import OpenAICompatProvider
from cococat.providers.anthropic import AnthropicProvider
from cococat.providers.credentials import CredentialManager
from cococat.providers.registry import ProviderRegistry, ProviderSpec, create_builtin_registry

logger = logging.getLogger("cococat.providers")


class ProviderFactory:
    """Creates LLM providers based on configuration."""

    def __init__(
        self,
        credential_manager: CredentialManager | None = None,
        registry: ProviderRegistry | None = None,
    ):
        self._credentials = credential_manager or CredentialManager()
        self._registry = registry or create_builtin_registry()

    def _find_spec(self, model: str) -> ProviderSpec | None:
        """Find the best matching provider spec for a model string."""
        spec = (
            self._registry.find_by_name(model)
            or self._registry.find_by_model(model)
        )
        if not spec:
            for s in self._registry.list_all():
                key = self._credentials.get(s.name)
                if key:
                    return s
        return spec

    def _resolve_api_key(self, spec: ProviderSpec) -> str | None:
        """Resolve API key: personal credential manager → admin fallback → env var."""
        key = self._credentials.get(spec.name)
        if key:
            return key

        # Fallback: admin's shared key
        from cococat.config_store import ConfigStore
        from cococat.providers.credentials import CredentialManager
        admin_store = ConfigStore(user_id="admin")
        admin_creds = CredentialManager(config_store=admin_store)
        key = admin_creds.get(spec.name)
        if key:
            return key

        if spec.env_key:
            return os.environ.get(spec.env_key) or None
        return None

    def _build_provider(self, spec: ProviderSpec, model: str, api_key: str, **overrides) -> BaseProvider:
        base_url = overrides.get("base_url", spec.default_api_base)
        effective_model = overrides.get("model", model)

        if spec.backend == "anthropic":
            return AnthropicProvider(
                api_key=api_key,
                model=effective_model,
                base_url=base_url,
            )
        return OpenAICompatProvider(
            api_key=api_key,
            base_url=base_url,
            model=effective_model,
            provider_name=spec.name,
        )

    async def create(self, model: str, **overrides) -> BaseProvider | None:
        """Create a provider for the given model.

        Priority:
        1. Direct spec by name match
        2. Model keyword match
        3. First provider with any API key
        """
        spec = self._find_spec(model)
        if not spec:
            logger.error("No provider found for model '%s'", model)
            return None

        api_key = self._resolve_api_key(spec)
        if not api_key:
            logger.error("No API key for provider '%s'", spec.name)
            return None

        return self._build_provider(spec, model, api_key, **overrides)

    def create_sync(self, model: str, **overrides) -> BaseProvider | None:
        """Synchronous version for non-async contexts."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            return None

        spec = self._find_spec(model)
        if not spec:
            return None

        api_key = self._resolve_api_key(spec)
        if not api_key:
            return None

        return self._build_provider(spec, model, api_key, **overrides)
