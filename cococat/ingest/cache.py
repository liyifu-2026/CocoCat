"""KB ingest cache — SHA256 hash of source → written file list."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger("cococat.kb.cache")


class IngestCache:
    """SHA256-based cache for KB ingest results.

    If a source file's hash hasn't changed AND all previously written files
    still exist on disk, skip the LLM pipeline entirely.
    """

    def __init__(self, cache_dir: str):
        self._dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._path = os.path.join(cache_dir, "ingest-cache.json")
        self._data: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, content_hash: str) -> Optional[list[str]]:
        """Get cached file list for a hash if all files still exist."""
        files = self._data.get(content_hash)
        if not files:
            return None

        # Verify all files still exist
        for fpath in files:
            if not os.path.exists(fpath):
                return None

        return files

    def set(self, content_hash: str, files: list[str]) -> None:
        """Store hash → file list mapping."""
        self._data[content_hash] = files
        self._save()

    def remove(self, content_hash: str) -> None:
        """Remove a cache entry."""
        self._data.pop(content_hash, None)
        self._save()
