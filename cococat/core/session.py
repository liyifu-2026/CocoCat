"""Session model — JSONL conversation files with LRU caching."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections import OrderedDict


class Session:
    """A single conversation session stored as a JSONL file."""

    def __init__(self, session_id: str, dir_path: str):
        self.id = session_id
        self._dir = dir_path
        self._path = os.path.join(dir_path, f"{session_id}.jsonl")
        self._closed = False

    @property
    def path(self) -> str:
        return self._path

    async def append(self, role: str, content: str) -> None:
        """Append a message to the session JSONL file."""
        if self._closed:
            raise RuntimeError("Session is closed.")
        os.makedirs(self._dir, exist_ok=True)
        entry = {"role": role, "content": content}
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def read(self) -> list[dict]:
        """Read all messages from the session JSONL file."""
        if not os.path.exists(self._path):
            return []
        messages = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages

    async def close(self) -> None:
        """Mark session as closed. Future appends are rejected."""
        self._closed = True

    async def sanitized_read(self, max_lines: int = 30) -> list[dict]:
        """Read last N user/assistant messages, skipping system and tool roles.

        Equivalent to the old _load_session() function in agent.py.
        """
        messages = await self.read()
        filtered = [
            {"role": m["role"], "content": m.get("content", "")}
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]
        return filtered[-max_lines:]

    async def append_pair(self, user_msg: str, assistant_reply: str) -> None:
        """Append a user message and assistant reply in one call.

        Equivalent to the old _save_session_pair() function in agent.py.
        """
        await self.append("user", user_msg)
        await self.append("assistant", assistant_reply)


class SessionManager:
    """Manages Session lifecycle with LRU caching."""

    def __init__(self, max_cached: int = 10):
        self._cache: OrderedDict[str, Session] = OrderedDict()
        self._max_cached = max_cached

    async def create(
        self, dir_path: str, system_prompt: str | None = None
    ) -> Session:
        """Create a new session."""
        session_id = uuid.uuid4().hex[:16]
        session = Session(session_id, dir_path)
        if system_prompt:
            await session.append("system", system_prompt)
        self._add_to_cache(session)
        return session

    async def open(self, session_id: str, dir_path: str) -> Session:
        """Open an existing session by ID."""
        if session_id in self._cache:
            self._cache.move_to_end(session_id)
            return self._cache[session_id]

        session = Session(session_id, dir_path)
        if not os.path.exists(session.path):
            raise FileNotFoundError(f"Session file not found: {session.path}")
        self._add_to_cache(session)
        return session

    def _add_to_cache(self, session: Session) -> None:
        if len(self._cache) >= self._max_cached:
            self._cache.popitem(last=False)  # evict oldest
        self._cache[session.id] = session


# ── Module-level helpers (fallback when no Session object is available) ──

def load_session(path: str, max_lines: int = 30) -> list[dict]:
    """Read last N user/assistant messages from a JSONL session file."""
    if not os.path.exists(path):
        return []
    messages = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("role") in ("user", "assistant"):
                        messages.append({"role": msg["role"], "content": msg.get("content", "")})
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return messages[-max_lines:]


def save_session_pair(path: str, user_msg: str, assistant_reply: str) -> None:
    """Append a user/assistant pair to a session JSONL file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"role": "user", "content": user_msg}, ensure_ascii=False) + "\n")
        f.write(json.dumps({"role": "assistant", "content": assistant_reply}, ensure_ascii=False) + "\n")


def maybe_trigger_dream(session_path: str) -> None:
    """Fire-and-forget auto-dream if session has enough history."""
    if not os.path.exists(session_path):
        return
    with open(session_path, encoding="utf-8") as f:
        line_count = sum(1 for _ in f)
    if line_count < 50:
        return

    async def _dream():
        from cococat.memory.store import MemoryStore
        store = MemoryStore()
        try:
            await store.dream(session_path)
        except Exception:
            import logging
            logger = logging.getLogger("cococat.dream")
            logger.warning("auto_dream failed, retry next session", exc_info=True)

    asyncio.create_task(_dream())
