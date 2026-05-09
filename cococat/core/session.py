"""Session model — JSONL conversation files with LRU caching."""

from __future__ import annotations

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
