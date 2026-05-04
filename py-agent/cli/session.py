"""Chat session persistence (JSONL history)."""
import json
import time
from pathlib import Path

SESSIONS_DIR = Path.home() / ".cococat" / "sessions"


class Session:
    """A chat session with message history persisted to JSONL."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.key = f"{agent_id}_{int(time.time())}"
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
        session = cls(agent_id)
        session.key = key
        session._path = path
        session.messages = []
        for line in path.read_text().splitlines():
            if line.strip():
                try:
                    session.messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        session._loaded = True
        return session

    @classmethod
    def list_sessions(cls) -> list[str]:
        if not SESSIONS_DIR.exists():
            return []
        return sorted(
            [f.stem for f in SESSIONS_DIR.glob("*.jsonl")],
            reverse=True,
        )
