"""Chat group reader for agent heartbeat — reads new messages and processes them."""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))


def _load_groups():
    path = os.path.join(BASE, "..", "chat", "groups.json")
    if not os.path.exists(path):
        return []
    try:
        data = json.loads(open(path, "r", encoding="utf-8").read())
        return data.get("groups", [])
    except Exception:
        return []


def _get_messages(group_id: str) -> list[dict]:
    path = os.path.join(BASE, "..", "chat", group_id, "messages.jsonl")
    if not os.path.exists(path):
        return []
    msgs = []
    try:
        for line in open(path, "r", encoding="utf-8").read().strip().split("\n"):
            line = line.strip()
            if line:
                msgs.append(json.loads(line))
    except Exception:
        pass
    return msgs


def _save_messages(group_id: str, messages: list[dict]):
    path = os.path.join(BASE, "..", "chat", group_id, "messages.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


def _calc_priority(content: str, sender: str, agent_id: str) -> int:
    score = 0
    lower = content.lower()
    if f"@{agent_id.lower()}" in lower:
        score += 100
    if "@all" in lower or "@全体成员" in lower or "@所有人" in lower:
        score += 80
    if sender == "admin":
        score += 50
    if sender == "leader":
        score += 30
    return score


def get_unread_messages(agent_id: str) -> list[dict]:
    groups = _load_groups()
    unread = []

    for group in groups:
        member_ids = [m["id"] for m in group.get("members", [])]
        if agent_id not in member_ids:
            continue

        messages = _get_messages(group["id"])
        for i, msg in enumerate(messages):
            if msg.get("recalled"):
                continue
            read_by = msg.get("read_by", [])
            if any(r["agent_id"] == agent_id for r in read_by):
                continue

            score = _calc_priority(msg.get("content", ""), msg.get("from", ""), agent_id)
            if score < 30:
                continue

            unread.append({
                "group_id": group["id"],
                "group_name": group.get("name", group["id"]),
                "msg_index": i,
                "from": msg.get("from", ""),
                "content": msg.get("content", ""),
                "score": score,
                "msg": msg,
            })

    unread.sort(key=lambda x: -x["score"])
    return unread


def mark_as_read(agent_id: str, group_id: str, msg_index: int, score: int):
    from sandbox import FileLock
    messages_path = os.path.join(BASE, "..", "chat", group_id, "messages.jsonl")
    if not os.path.exists(messages_path):
        return
    with FileLock(messages_path):
        with open(messages_path, "r", encoding="utf-8") as f:
            messages = []
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        if msg_index < 0 or msg_index >= len(messages):
            return
        msg = messages[msg_index]
        if "read_by" not in msg:
            msg["read_by"] = []
        if not any(r["agent_id"] == agent_id for r in msg["read_by"]):
            msg["read_by"].append({
                "agent_id": agent_id,
                "read_at": __import__("datetime").datetime.now().isoformat(),
                "score": score,
            })
            messages[msg_index] = msg
            with open(messages_path, "w", encoding="utf-8") as f:
                for m in messages:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")


def get_agent_cursor(agent_id: str) -> str:
    """Get the last msg_id this agent has processed."""
    path = os.path.join("chat", "cursors", f"{agent_id}.txt")
    if os.path.exists(path):
        return open(path).read().strip()
    return ""


def set_agent_cursor(agent_id: str, msg_id: str):
    """Set the last msg_id this agent has processed."""
    path = os.path.join("chat", "cursors", f"{agent_id}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(msg_id)
