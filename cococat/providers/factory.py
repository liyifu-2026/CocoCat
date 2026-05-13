"""Provider factory — creates LLM providers from config."""

from __future__ import annotations

import logging

from cococat.providers.base import BaseProvider
from cococat.providers.openai_compat import OpenAICompatProvider
from cococat.providers.anthropic import AnthropicProvider
from cococat.providers.credentials import CredentialManager
from cococat.providers.registry import create_builtin_registry

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

    async def create(self, model: str, **overrides) -> BaseProvider | None:
        """Create a provider for the given model.

        Priority:
        1. Direct spec by name match
        2. Model keyword match
        3. First provider with any API key
        """
        spec = (
            self._registry.find_by_name(model)
            or self._registry.find_by_model(model)
        )
        if not spec:
            # Try first provider with any key configured
            for s in self._registry.list_all():
                key = self._credentials.get(s["name"])
                if key:
                    spec = s
                    break

        if not spec:
            logger.error("No provider found for model '%s'", model)
            return None

        api_key = self._credentials.get(spec["name"])
        if not api_key:
            # Try env var
            import os
            env_key = spec.get("env_key", "")
            api_key = os.environ.get(env_key, "") if env_key else ""

        if not api_key:
            logger.error("No API key for provider '%s'", spec["name"])
            return None

        base_url = overrides.get("base_url", spec["base_url"])

        return OpenAICompatProvider(
            api_key=api_key,
            base_url=base_url,
            model=overrides.get("model", model),
        )

    def create_sync(self, model: str, **overrides) -> BaseProvider | None:
        """Synchronous version — skips async initialization."""
        spec = (
            self._registry.find_by_name(model)
            or self._registry.find_by_model(model)
        )
        if not spec:
            return None

        import os
        api_key = self._credentials.get(spec["name"])
        if not api_key:
            env_key = spec.get("env_key", "")
            api_key = os.environ.get(env_key, "") if env_key else ""

        if not api_key:
            return None

        if spec.get("backend") == "anthropic":
            return AnthropicProvider(
                api_key=api_key,
                model=model,
                base_url=spec.get("base_url", "https://api.anthropic.com"),
            )

        return OpenAICompatProvider(
            api_key=api_key,
            base_url=spec["base_url"],
            model=model,
        )
