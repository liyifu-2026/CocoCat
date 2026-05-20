"""Session summarization — token-threshold-based compression to prevent context overflow."""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger("cococat.memory.summarize")

TOKEN_THRESHOLD = int(os.environ.get("COCOCAT_SUMMARIZE_TOKEN_THRESHOLD", "8000"))
IDLE_MINUTES = int(os.environ.get("COCOCAT_SUMMARIZE_IDLE_MINUTES", "30"))


async def compress_session(
    messages: list[dict],
    session_id: str,
    summary_dir: str = "memory/summaries",
    get_llm: Callable[[], Any] | None = None,
    last_activity: float | None = None,
) -> list[dict]:
    """Compress oldest messages into summary if token count exceeds threshold.

    Returns a new messages list (does not mutate input).
    """
    approx_tokens = _count_tokens(messages)
    is_idle = last_activity and (time.time() - last_activity) > IDLE_MINUTES * 60

    if approx_tokens <= TOKEN_THRESHOLD and not is_idle:
        return messages

    # Load existing summaries
    existing = _load_summaries(session_id, summary_dir)

    # Find cutoff: keep most recent ~3000 tokens, compress the rest
    target = 3000
    cutoff = len(messages)
    running = 0
    for i in range(len(messages) - 1, -1, -1):
        running += _msg_tokens(messages[i])
        if running >= target:
            cutoff = i
            break

    if cutoff <= 0:
        return messages

    old_msgs = messages[:cutoff]
    recent_msgs = messages[cutoff:]

    # Compress
    llm = get_llm() if get_llm else None
    if not llm:
        return messages

    old_text = "\n".join(
        f"[{m['role']}]: {m.get('content', '')[:800]}"
        for m in old_msgs[-30:]
    )

    existing_text = ""
    for s in existing[-5:]:
        existing_text += f"\n[{s['at']}] {s['summary']}"

    prompt = (
        "Synthesize the following into a concise running summary. "
        "Keep all key facts, decisions, user preferences, and relevant context. "
        "Merge with prior summaries — do not repeat information.\n\n"
        f"### Prior summaries\n{existing_text or '(none)'}\n\n"
        f"### New conversation\n{old_text}\n\n"
        "Updated running summary:"
    )

    try:
        result = await llm.chat(messages=[{"role": "user", "content": prompt}])
        summary_text = (result.content or "")[:1500]
    except Exception:
        logger.exception("compress_session: LLM call failed")
        return messages

    if not summary_text.strip():
        return messages

    # Save entry
    entry = {
        "at": datetime.now().isoformat(),
        "summary": summary_text,
        "messages_compressed": len(old_msgs),
    }
    _save_summary(session_id, existing + [entry], summary_dir)

    # Build new messages — ensure total is under threshold
    summary_msg = {"role": "system", "content": _build_summary_prompt(existing + [entry])}
    new_messages = [messages[0], summary_msg] + recent_msgs if messages else [summary_msg] + recent_msgs

    # Trim recent if total still exceeds threshold
    while _count_tokens(new_messages) > TOKEN_THRESHOLD and len(recent_msgs) > 5:
        recent_msgs = recent_msgs[1:]
        new_messages = [messages[0], summary_msg] + recent_msgs if messages else [summary_msg] + recent_msgs

    return new_messages


def _count_tokens(messages: list[dict]) -> int:
    return sum(_msg_tokens(m) for m in messages)


def _msg_tokens(msg: dict) -> int:
    content = msg.get("content", "")
    return max(1, len(content) // 3)


def _load_summaries(session_id: str, summary_dir: str) -> list[dict]:
    path = os.path.join(summary_dir, f"{session_id}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_summary(session_id: str, entries: list[dict], summary_dir: str) -> None:
    os.makedirs(summary_dir, exist_ok=True)
    path = os.path.join(summary_dir, f"{session_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def _build_summary_prompt(entries: list[dict]) -> str:
    lines = []
    for s in entries[-5:]:
        at = s["at"][:16]
        lines.append(f"[{at}] {s['summary']}")
    return "## Prior Conversation Summary\n" + "\n\n".join(lines)


# ── backward compat ────────────────────────────────────────

class SummarizeMemory:
    """Backward-compat wrapper — delegates to compress_session."""

    def __init__(self, memory_dir: str = "memory", get_llm: Callable[[], Any] | None = None):
        self._memory_dir = memory_dir
        self._get_llm = get_llm or (lambda: None)

    async def notify_turn(self, session: Any) -> None:
        pass

    async def notify_session_end(self, session: Any) -> None:
        pass

    @staticmethod
    def _hash_messages(messages: list[dict]) -> str:
        import hashlib
        text = json.dumps(
            [{"r": m["role"], "c": m.get("content", "")[:200]} for m in messages[-20:]],
            sort_keys=True,
        )
        return hashlib.sha256(text.encode()).hexdigest()[:16]
