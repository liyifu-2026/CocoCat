"""Credential manager — reads API keys from ConfigStore or auth.json with ${ENV_VAR} support."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.config_store import ConfigStore

logger = logging.getLogger("cococat.providers.credentials")

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


class CredentialManager:
    """Loads provider API keys from ConfigStore or auth.json.

    When a ConfigStore is provided, delegates all reads to it (single source of truth).
    When no ConfigStore is available, reads auth.json directly.
    Keys can be literal strings or ${ENV_VAR} references resolved at read time.
    """

    def __init__(self, path: str = "config/auth.json", config_store: "ConfigStore | None" = None):
        self._path = path
        self._config_store = config_store
        self._data: dict[str, str] = {}
        if not config_store:
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
        if self._config_store is not None:
            raw = self._config_store.get_auth(provider_name)
        else:
            raw = self._data.get(provider_name)
        if raw is None:
            return None
        return _ENV_VAR_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), ""),
            raw,
        )
