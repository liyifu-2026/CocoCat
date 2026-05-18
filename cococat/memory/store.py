"""MemoryStore — unified memory: file-based + SQLite FTS5, manual + automated."""

from __future__ import annotations

import logging
from typing import Any

from cococat.memory.manual import _ManualMixin
from cococat.memory.dream import _DreamMixin
from cococat.memory.summarize import _SummarizeMixin
from cococat.memory.compile import _CompileMixin
from cococat.memory.facts import _FactsMixin

logger = logging.getLogger("cococat.memory")

_DREAM_MODEL_CANDIDATES = ["deepseek-chat"]


class MemoryStore(_ManualMixin, _DreamMixin, _SummarizeMixin, _CompileMixin, _FactsMixin):
    """Unified memory layer.

    Sub-modules:
      manual    — remember / recall / forget / pin / experiences
      dream     — auto-extract facts from conversation sessions
      summarize — on-the-fly session summarization (Ticker)
      compile   — periodic daily → weekly → longterm compilation
      facts     — FTS5 atomic fact extraction and indexing
    """

    def __init__(self, llm: Any = None, db: Any = None, memory_dir: str = "memory"):
        self._llm = llm
        self._db = db
        self._memory_dir = memory_dir
        self._turn_counts: dict[str, int] = {}
        self._fingerprints: dict[str, str] = {}
        self._fact_snapshots: dict[str, str] = {}

    def _get_llm(self):
        if self._llm:
            return self._llm
        from cococat.providers.factory import ProviderFactory
        from cococat.providers.credentials import CredentialManager
        creds = CredentialManager()
        factory = ProviderFactory(credential_manager=creds)
        for model in _DREAM_MODEL_CANDIDATES:
            provider = factory.create_sync(model)
            if provider:
                return provider
        for spec in factory._registry.list_all():
            provider = factory.create_sync(spec["name"])
            if provider:
                return provider
        return None
