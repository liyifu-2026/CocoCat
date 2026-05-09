"""Credential manager — reads API keys from auth.json with ${ENV_VAR} support."""

from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger("cococat.providers.credentials")

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


class CredentialManager:
    """Loads provider API keys from auth.json.

    Keys can be literal strings or ${ENV_VAR} references resolved at read time.
    """

    def __init__(self, path: str = "config/auth.json"):
        self._path = path
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                self._data = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to load auth.json from %s", self._path)

    def get(self, provider_name: str) -> str | None:
        """Get API key for a provider. Returns None if not found."""
        raw = self._data.get(provider_name)
        if raw is None:
            return None
        # Resolve ${ENV_VAR} references
        return _ENV_VAR_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), ""),
            raw,
        )
