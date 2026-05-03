"""Chat group management with priority-scored messaging and token-budgeted context."""
import json
import re
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CHAT_DIR = BASE_DIR / "chat"


def _init_default_group():
    """Create the default 'all hands' group if it doesn't exist."""
    groups_file = CHAT_DIR / "groups.json"
    if groups_file.exists():
        return
    CHAT_DIR.mkdir(parents=True, exist_ok=True)

    # Load all agents from config
    import tomllib
    config_path = BASE_DIR / "agents" / "config.toml"
    members = []
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for a in data.get("agents", []):
            members.append({"id": a["id"], "name": a["name"], "role": "member"})

    groups = [
        {
            "id": "general",
            "name": "General",
            "announcement": "Default group chat for all team members.",
            "created_at": datetime.now().isoformat(),
            "is_default": True,
            "members": [{"id": "admin", "name": "Admin", "role": "owner"}] + members,
        }
    ]
    groups_file.write_text(json.dumps({"groups": groups}, ensure_ascii=False, indent=2), encoding="utf-8")

    # Create messages file
    msg_dir = CHAT_DIR / "general"
    msg_dir.mkdir(parents=True, exist_ok=True)
    (msg_dir / "messages.jsonl").write_text("", encoding="utf-8")


def _load_groups():
    groups_file = CHAT_DIR / "groups.json"
    if not groups_file.exists():
        _init_default_group()
    return json.loads(groups_file.read_text(encoding="utf-8"))


def _save_groups(data: dict):
    groups_file = CHAT_DIR / "groups.json"
    groups_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _calc_priority(msg_body: str, from_id: str, mentions: list[str], agent_id: str | None = None) -> int:
    score = 0
    body_lower = msg_body.lower()

    # @mentions score
    if agent_id and f"@{agent_id}" in body_lower:
        score += 100
    if any(f"@{m}" in body_lower for m in mentions):
        pass  # handled in loop above

    if "@all" in body_lower or "@全体成员" in body_lower or "@所有人" in body_lower:
        score += 80

    # Sender priority
    if from_id == "admin":
        score += 50
    if from_id == "leader":
        score += 30

    # recency: scored at query time, not stored

    return score


def _estimate_tokens(text: str) -> int:
    """Rough token estimation."""
    return len(text) // 4 + 1


def _get_prioritized_context(group_id: str, agent_id: str, budget: int = 3000, digest_budget: int = 1000) -> dict:
    """Get priority-scored, token-budgeted messages for a specific agent."""
    msg_dir = CHAT_DIR / group_id / "messages.jsonl"
    if not msg_dir.exists():
        return {"messages": [], "digest": ""}

    messages = []
    try:
        for line in msg_dir.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if line:
                msg = json.loads(line)
                # Calculate priority for this agent
                msg["priority_score"] = _calc_priority(
                    msg.get("content", ""),
                    msg.get("from", ""),
                    msg.get("mentions", []),
                    agent_id,
                )
                messages.append(msg)
    except Exception:
        return {"messages": [], "digest": ""}

    # Sort by priority descending, then by timestamp descending for ties
    messages.sort(key=lambda m: (-m["priority_score"], m.get("timestamp", "")))

    # Take messages within token budget
    result_msgs = []
    used = 0
    remaining = []
    for m in messages:
        tokens = m.get("token_count", _estimate_tokens(m.get("content", "")))
        if used + tokens <= budget:
            result_msgs.append(m)
            used += tokens
        else:
            remaining.append(m)

    # Build digest from remaining messages
    digest_parts = []
    digest_used = 0
    for m in reversed(remaining):
        tokens = m.get("token_count", _estimate_tokens(m.get("content", "")))
        if digest_used + tokens <= digest_budget:
            ts = m.get("timestamp", "")[:16]
            sender = m.get("from", "?")
            content = m.get("content", "")[:80]
            line = f"[{ts}] {sender}: {content}"
            digest_parts.append(line)
            digest_used += tokens

    return {
        "messages": result_msgs,
        "digest": "\n".join(reversed(digest_parts)) if digest_parts else "",
    }


@router.get("/api/chat/groups")
def list_groups():
    """List all chat groups."""
    data = _load_groups()
    return data


@router.post("/api/chat/groups")
def create_group(body: dict):
    """Create a new chat group."""
    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)

    data = _load_groups()
    group_id = name.lower().replace(" ", "-")
    existing = {g["id"] for g in data["groups"]}
    if group_id in existing:
        suffix = 1
        while f"{group_id}-{suffix}" in existing:
            suffix += 1
        group_id = f"{group_id}-{suffix}"

    members = body.get("members", [])
    announcement = body.get("announcement", "")

    new_group = {
        "id": group_id,
        "name": name,
        "announcement": announcement,
        "created_at": datetime.now().isoformat(),
        "is_default": False,
        "members": [{"id": "admin", "name": "Admin", "role": "owner"}] + members,
    }
    data["groups"].append(new_group)
    _save_groups(data)

    # Create message file
    msg_dir = CHAT_DIR / group_id
    msg_dir.mkdir(parents=True, exist_ok=True)
    (msg_dir / "messages.jsonl").write_text("", encoding="utf-8")

    return {"status": "created", "group": new_group}


@router.get("/api/chat/groups/{group_id}")
def get_group(group_id: str):
    """Get a single group's detail."""
    data = _load_groups()
    for g in data["groups"]:
        if g["id"] == group_id:
            return g
    return JSONResponse({"error": "group not found"}, status_code=404)


@router.patch("/api/chat/groups/{group_id}")
def update_group(group_id: str, body: dict):
    """Update group name or announcement."""
    data = _load_groups()
    for g in data["groups"]:
        if g["id"] == group_id:
            if "name" in body:
                g["name"] = body["name"]
            if "announcement" in body:
                g["announcement"] = body["announcement"]
            _save_groups(data)
            return {"status": "updated", "group": g}
    return JSONResponse({"error": "group not found"}, status_code=404)


@router.post("/api/chat/groups/{group_id}/members")
def add_member(group_id: str, body: dict):
    """Add a member to a group."""
    data = _load_groups()
    for g in data["groups"]:
        if g["id"] == group_id:
            agent_id = body.get("agent_id", "")
            name = body.get("name", agent_id)
            if any(m["id"] == agent_id for m in g["members"]):
                return JSONResponse({"error": "member already exists"}, status_code=409)
            g["members"].append({"id": agent_id, "name": name, "role": "member"})
            _save_groups(data)
            return {"status": "added", "group": g}
    return JSONResponse({"error": "group not found"}, status_code=404)


@router.delete("/api/chat/groups/{group_id}/members/{agent_id}")
def remove_member(group_id: str, agent_id: str):
    """Remove a member from a group."""
    if agent_id == "admin":
        return JSONResponse({"error": "cannot remove admin"}, status_code=400)
    data = _load_groups()
    for g in data["groups"]:
        if g["id"] == group_id:
            if g.get("is_default") and agent_id in [m["id"] for m in g["members"]]:
                return JSONResponse({"error": "cannot remove from default group"}, status_code=400)
            g["members"] = [m for m in g["members"] if m["id"] != agent_id]
            _save_groups(data)
            return {"status": "removed", "group": g}
    return JSONResponse({"error": "group not found"}, status_code=404)


@router.delete("/api/chat/groups/{group_id}")
def delete_group(group_id: str):
    """Delete a group (except default)."""
    data = _load_groups()
    for g in data["groups"]:
        if g["id"] == group_id:
            if g.get("is_default"):
                return JSONResponse({"error": "cannot delete default group"}, status_code=400)
            data["groups"] = [x for x in data["groups"] if x["id"] != group_id]
            _save_groups(data)
            # Remove message files
            import shutil
            shutil.rmtree(CHAT_DIR / group_id, ignore_errors=True)
            return {"status": "deleted"}
    return JSONResponse({"error": "group not found"}, status_code=404)


@router.post("/api/chat/groups/{group_id}/messages")
def send_message(group_id: str, body: dict):
    """Send a message to a group."""
    content = body.get("content", "").strip()
    from_id = body.get("from", "admin")
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    msg_dir = CHAT_DIR / group_id
    msg_dir.mkdir(parents=True, exist_ok=True)
    msg_file = msg_dir / "messages.jsonl"

    # Detect mentions
    mentions = re.findall(r"@(\w+)", content)

    entry = {
        "from": from_id,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "priority_score": 0,
        "token_count": _estimate_tokens(content),
        "mentions": mentions,
        "recalled": False,
        "read_by": [],
    }
    with open(msg_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {"status": "sent", "message": entry}


@router.post("/api/chat/groups/{group_id}/messages/{msg_index}/recall")
def recall_message(group_id: str, msg_index: int):
    """Recall a message by marking it as recalled."""
    msg_file = CHAT_DIR / group_id / "messages.jsonl"
    if not msg_file.exists():
        return JSONResponse({"error": "group not found"}, status_code=404)

    try:
        lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
        if msg_index < 0 or msg_index >= len(lines):
            return JSONResponse({"error": "message not found"}, status_code=404)

        msg = json.loads(lines[msg_index])
        msg["recalled"] = True
        lines[msg_index] = json.dumps(msg, ensure_ascii=False)
        msg_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"status": "recalled"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/chat/groups/{group_id}/messages/{msg_index}/read")
def mark_message_read(group_id: str, msg_index: int, body: dict):
    """Mark a message as read by an agent, recording priority score."""
    agent_id = body.get("agent_id", "")
    score = body.get("score", 0)
    if not agent_id:
        return JSONResponse({"error": "agent_id is required"}, status_code=400)

    msg_file = CHAT_DIR / group_id / "messages.jsonl"
    if not msg_file.exists():
        return JSONResponse({"error": "group not found"}, status_code=404)

    try:
        lines = msg_file.read_text(encoding="utf-8").strip().split("\n")
        if msg_index < 0 or msg_index >= len(lines):
            return JSONResponse({"error": "message not found"}, status_code=404)

        msg = json.loads(lines[msg_index])
        if "read_by" not in msg:
            msg["read_by"] = []

        if not any(r["agent_id"] == agent_id for r in msg["read_by"]):
            msg["read_by"].append({
                "agent_id": agent_id,
                "read_at": datetime.now().isoformat(),
                "score": score,
            })

        lines[msg_index] = json.dumps(msg, ensure_ascii=False)
        msg_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"status": "read", "read_by": msg["read_by"]}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/chat/groups/{group_id}/messages")
def get_messages(group_id: str, limit: int = 50):
    """Get recent messages for a group (raw, newest first)."""
    msg_file = CHAT_DIR / group_id / "messages.jsonl"
    if not msg_file.exists():
        return {"messages": []}
    messages = []
    try:
        for line in msg_file.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if line:
                messages.append(json.loads(line))
    except Exception:
        pass
    return {"messages": messages[-limit:]}


@router.get("/api/chat/groups/{group_id}/context/{agent_id}")
def get_agent_context(group_id: str, agent_id: str):
    """Get priority-scored, token-budgeted context for an agent."""
    result = _get_prioritized_context(group_id, agent_id, budget=3000, digest_budget=1000)
    return result


# Initialize default group on import
_init_default_group()
