"""Auto-Dream — automatic memory extraction from conversation history.

Fire-and-forget: after N rounds of conversation, a cheap LLM reads the full
session log and pins key facts into memory/memory.md. The next session
starts with these facts already in the system prompt without re-reading
raw history.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("cococat.dream")

DREAM_THRESHOLD = 50
KEEP_LINES = 30

_DREAM_MODEL_CANDIDATES = [
    "deepseek-chat",
]


async def try_auto_dream(agent, session_path: str) -> None:
    """Extract key facts from session history and pin to memory.md.

    Designed to run as `asyncio.create_task()` — failure is silent,
    next session will retry.
    """
    try:
        if not os.path.exists(session_path):
            return

        with open(session_path, encoding="utf-8") as f:
            lines = f.readlines()

        if len(lines) < DREAM_THRESHOLD:
            return

        session_content = "".join(lines)

        memory_path = _memory_path_for(session_path)
        existing_memory = _read_file(memory_path)

        llm = _get_dream_llm()
        if not llm:
            logger.warning("auto_dream: no LLM available, retry next session")
            return

        prompt = _build_prompt(session_content, existing_memory)
        resp = await llm.chat([{"role": "user", "content": prompt}])
        raw = resp.content or ""

        pinned = 0
        for line in raw.splitlines():
            fact = line.strip()
            if not fact:
                continue
            if fact in existing_memory:
                continue
            os.makedirs(os.path.dirname(memory_path) or ".", exist_ok=True)
            with open(memory_path, "a", encoding="utf-8") as f:
                f.write(fact + "\n")
            existing_memory += fact + "\n"
            pinned += 1

        if pinned:
            logger.info("auto_dream: pinned %d facts → %s", pinned, memory_path)

        _truncate_session(session_path, KEEP_LINES)
        logger.debug("auto_dream: truncated %s to %d lines", session_path, KEEP_LINES)

    except Exception:
        logger.warning("auto_dream failed, retry next session", exc_info=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _memory_path_for(session_path: str) -> str:
    return os.path.join(os.path.dirname(session_path), "memory", "memory.md")


def _read_file(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _build_prompt(session_history: str, existing_memory: str) -> str:
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


def _truncate_session(path: str, keep: int) -> None:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) <= keep:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines[-keep:])


def _get_dream_llm():
    """Return the cheapest available LLM provider for dream extraction."""
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
