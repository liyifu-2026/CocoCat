from __future__ import annotations

import logging
from typing import Any

from cococat.memory.manual import ManualMemory
from cococat.memory.dream import DreamMemory
from cococat.memory.summarize import SummarizeMemory
from cococat.memory.compile import CompileMemory

logger = logging.getLogger("cococat.memory")

_DREAM_MODEL_CANDIDATES = ["deepseek-chat"]


class MemoryStore:
    """Unified memory layer — 4 sub-systems.

    Sub-modules (explicit composition, no mixins):
      manual    — remember / recall / forget / pin
      dream     — auto-extract facts from conversation sessions
      summarize — on-the-fly session summarization (Ticker)
      compile   — periodic daily → weekly → longterm compilation
    """

    def __init__(self, llm: Any = None, db: Any = None, memory_dir: str = "memory"):
        get_llm = self._get_llm

        self._manual = ManualMemory(memory_dir=memory_dir, db=db)
        self._dream = DreamMemory(get_llm=get_llm)
        self._summarize = SummarizeMemory(memory_dir=memory_dir, get_llm=get_llm)
        self._compile = CompileMemory(memory_dir=memory_dir, get_llm=get_llm)

        self._llm = llm
        self._db = db
        self._memory_dir = memory_dir

    # ── public API ───────────────────────────────────────────

    # manual
    def remember(self, text: str, category: str | None = None, exp_path: str = "") -> str:
        return self._manual.remember(text, category, exp_path)

    def recall(self, query: str) -> str:
        return self._manual.recall(query)

    def forget(self, keyword: str) -> str:
        return self._manual.forget(keyword)

    def load_for_system_prompt(self) -> str:
        return self._manual.load_for_system_prompt()

    # dream
    async def dream(self, session_path: str) -> None:
        return await self._dream.dream(session_path)

    # summarize
    async def notify_turn(self, session: Any) -> None:
        return await self._summarize.notify_turn(session)

    async def notify_session_end(self, session: Any) -> None:
        return await self._summarize.notify_session_end(session)

    # compile
    async def compile(self) -> None:
        return await self._compile.compile()

    async def compile_day(self) -> None:
        return await self._compile.compile_day()

    async def compile_week(self) -> None:
        return await self._compile.compile_week()

    async def compile_longterm(self) -> None:
        return await self._compile.compile_longterm()

    # ── internal helpers ──────────────────────────────────────

    def _pin(self, fact: str) -> str:
        return self._manual._pin(fact)

    @staticmethod
    def _dream_prompt(session_history: str, existing_memory: str) -> str:
        return DreamMemory._dream_prompt(session_history, existing_memory)

    def _memory_path_from_session(self, session_path: str) -> str:
        return self._dream._memory_path_from_session(session_path)

    @staticmethod
    def _hash_messages(messages: list[dict]) -> str:
        return SummarizeMemory._hash_messages(messages)

    def _load_summaries(self) -> list[dict]:
        return self._compile._load_summaries()

    # ── lazy LLM resolution ──────────────────────────────────

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
