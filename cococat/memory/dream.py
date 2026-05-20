"""Auto-dream — extract facts from conversation sessions into memory."""

from __future__ import annotations

import logging
import os
from typing import Callable, Any

logger = logging.getLogger("cococat.memory")

DREAM_THRESHOLD = 50
KEEP_LINES = 30


class DreamMemory:
    """Auto-extract facts from conversation sessions into memory.

    Dependencies are explicit: get_llm is a callable, not a hidden superclass method.
    """

    def __init__(self, get_llm: Callable[[], Any] | None = None):
        self._get_llm = get_llm or (lambda: None)

    async def dream(self, session_path: str) -> None:
        """Fire-and-forget: extract facts from session, pin to memory.md, truncate session."""
        try:
            if not os.path.exists(session_path):
                return

            with open(session_path, encoding="utf-8") as f:
                lines = f.readlines()

            if len(lines) < DREAM_THRESHOLD:
                return

            session_content = "".join(lines)
            memory_path = self._memory_path_from_session(session_path)
            existing = ""
            if os.path.exists(memory_path):
                with open(memory_path, encoding="utf-8") as f:
                    existing = f.read()

            llm = self._get_llm()
            if not llm:
                logger.warning("auto_dream: no LLM available")
                return

            prompt = self._dream_prompt(session_content, existing)
            resp = await llm.chat([{"role": "user", "content": prompt}])
            raw = resp.content or ""

            pinned = 0
            os.makedirs(os.path.dirname(memory_path) or ".", exist_ok=True)
            for line in raw.splitlines():
                fact = line.strip()
                if not fact or fact in existing:
                    continue
                with open(memory_path, "a", encoding="utf-8") as f:
                    f.write(fact + "\n")
                existing += fact + "\n"
                pinned += 1

            if pinned:
                logger.info("auto_dream: pinned %d facts → %s", pinned, memory_path)

        except Exception:
            logger.warning("auto_dream failed", exc_info=True)

    def _memory_path_from_session(self, session_path: str) -> str:
        return os.path.join(os.path.dirname(session_path), "memory", "memory.md")

    @staticmethod
    def _dream_prompt(session_history: str, existing_memory: str) -> str:
        memory_block = ""
        if existing_memory.strip():
            memory_block = (
                "\n## 已有记忆（不要重复输出）\n"
                f"{existing_memory.strip()}\n"
            )
        return (
            "你是一个记忆助手。从以下对话历史中提取迄今为止新发现的关键事实。\n"
            "每条不超过 30 字。只提取对后续对话有用的信息：\n"
            "用户偏好、项目信息、进行中的任务、重要决策、代码改动要点。\n"
            "不要提取闲聊内容。\n"
            f"{memory_block}\n"
            "对话历史：\n"
            f"{session_history[-8000:]}\n\n"
            "输出格式：严格每行一条事实，不要编号，不要前缀，不要空行。"
        )
