"""Chat session persistence (JSONL history) — nanobot SessionManager pattern."""
import json
import time
from pathlib import Path

SESSIONS_DIR = Path.home() / ".cococat" / "sessions"
SESSION_TTL_DAYS = 7


class Session:
    """A single chat session with message history."""

    def __init__(self, agent_id: str, key: str = ""):
        self.agent_id = agent_id
        self.key = key or f"{agent_id}_{int(time.time())}"
        self.messages: list[dict] = []
        self._path = SESSIONS_DIR / f"{self.key}.jsonl"
        self._loaded = False

    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        if self._path.parent.exists():
            line = json.dumps(self.messages[-1], ensure_ascii=False)
            with open(self._path, "a") as f:
                f.write(line + "\n")

    def save(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            for msg in self.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, key: str) -> "Session | None":
        path = SESSIONS_DIR / f"{key}.jsonl"
        if not path.exists():
            return None
        agent_id = key.split("_")[0] if "_" in key else key
        session = cls(agent_id, key=key)
        session._path = path
        for line in path.read_text().splitlines():
            if line.strip():
                try:
                    session.messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        session._loaded = True
        return session


class SessionManager:
    """Manages multiple sessions with lifecycle (nanobot SessionManager pattern)."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, agent_id: str, key: str = "") -> Session:
        if not key:
            recent = self.list_sessions(agent_id)
            if recent:
                loaded = Session.load(recent[0])
                if loaded:
                    self._sessions[loaded.key] = loaded
                    return loaded
        if key and key in self._sessions:
            return self._sessions[key]
        if key:
            loaded = Session.load(key)
            if loaded:
                self._sessions[key] = loaded
                return loaded
        session = Session(agent_id, key=key)
        if key:
            self._sessions[key] = session
        return session

    def save(self, session: Session):
        session.save()

    def flush_all(self) -> int:
        count = 0
        for session in self._sessions.values():
            if session.messages:
                session.save()
                count += 1
        return count

    @staticmethod
    def list_sessions(agent_id: str | None = None) -> list[str]:
        if not SESSIONS_DIR.exists():
            return []
        sessions = sorted(
            [f.stem for f in SESSIONS_DIR.glob("*.jsonl")],
            reverse=True,
        )
        if agent_id:
            return [s for s in sessions if s.startswith(agent_id)]
        return sessions

    @staticmethod
    def clean_expired(ttl_days: int = SESSION_TTL_DAYS) -> int:
        """Remove sessions older than ttl_days. Returns count removed."""
        if not SESSIONS_DIR.exists():
            return 0
        cutoff = time.time() - ttl_days * 86400
        removed = 0
        for f in SESSIONS_DIR.glob("*.jsonl"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        return removed
