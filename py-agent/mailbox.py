"""Agent mailbox system — inbox/outbox for inter-agent messaging."""
import os
import json
from datetime import datetime


def _mailbox_dir(agent_id: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "mailbox", agent_id)


def send_message(to_agent: str, from_agent: str, content: str) -> str:
    dir_path = _mailbox_dir(to_agent)
    os.makedirs(dir_path, exist_ok=True)
    inbox_path = os.path.join(dir_path, "inbox.jsonl")
    entry = {
        "from": from_agent,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "status": "unread",
    }
    with open(inbox_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return f"Message sent to {to_agent}"


def read_inbox(agent_id: str) -> list[dict]:
    inbox_path = os.path.join(_mailbox_dir(agent_id), "inbox.jsonl")
    if not os.path.exists(inbox_path):
        return []
    messages = []
    with open(inbox_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return messages


def mark_read(agent_id: str, idx: int):
    messages = read_inbox(agent_id)
    if 0 <= idx < len(messages):
        messages[idx]["status"] = "read"
    inbox_path = os.path.join(_mailbox_dir(agent_id), "inbox.jsonl")
    with open(inbox_path, "w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
