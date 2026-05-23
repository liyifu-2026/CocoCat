"""Session model — JSONL conversation files with LRU caching."""

from __future__ import annotations

import json
import os


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
        if content is None:
            content = ""
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
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return messages

    async def close(self) -> None:
        """Mark session as closed. Future appends are rejected."""
        self._closed = True

    async def sanitized_read(self, max_lines: int = 30) -> list[dict]:
        """Read last N user/assistant messages, skipping system and tool roles."""
        messages = await self.read()
        filtered = [
            {"role": m["role"], "content": m.get("content", "")}
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]
        return filtered[-max_lines:]

    async def append_pair(self, user_msg: str, assistant_reply: str) -> None:
        """Append a user message and assistant reply in one call."""
        await self.append("user", user_msg)
        await self.append("assistant", assistant_reply)


# ── Module-level helpers (backward compat, used by tests) ──

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


# ── LRU-cached session manager (used by tests) ──

from collections import OrderedDict
import uuid


class SessionManager:
    """Manages Session lifecycle with LRU caching."""

    def __init__(self, max_cached: int = 10):
        self._cache: OrderedDict[str, Session] = OrderedDict()
        self._max_cached = max_cached

    async def create(
        self, dir_path: str, system_prompt: str | None = None
    ) -> Session:
        session_id = uuid.uuid4().hex[:16]
        session = Session(session_id, dir_path)
        if system_prompt:
            await session.append("system", system_prompt)
        self._add_to_cache(session)
        return session

    async def open(self, session_id: str, dir_path: str) -> Session:
        if session_id in self._cache:
            session = self._cache[session_id]
            self._cache.move_to_end(session_id)
            session._closed = False
            return session

        session = Session(session_id, dir_path)
        if not os.path.exists(session.path):
            raise FileNotFoundError(f"Session file not found: {session.path}")
        self._add_to_cache(session)
        return session

    def _add_to_cache(self, session: Session) -> None:
        if len(self._cache) >= self._max_cached:
            self._cache.popitem(last=False)
        self._cache[session.id] = session
