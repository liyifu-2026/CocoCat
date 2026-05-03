"""Mailbox API routes — admin can view and send to agent mailboxes."""
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


@router.get("/api/mailbox")
def list_mailboxes():
    """List all agent mailboxes with unread counts and latest message."""
    mailbox_base = BASE_DIR / "agents" / "mailbox"
    config_path = BASE_DIR / "agents" / "config.toml"
    
    import tomllib
    agent_names = {}
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for a in data.get("agents", []):
            agent_names[a["id"]] = a["name"]
    
    mailboxes = []
    if mailbox_base.exists():
        for agent_dir in mailbox_base.iterdir():
            if not agent_dir.is_dir():
                continue
            inbox_path = agent_dir / "inbox.jsonl"
            unread = 0
            latest = None
            if inbox_path.exists():
                try:
                    lines = inbox_path.read_text(encoding="utf-8").strip().split("\n")
                    for line in lines:
                        if not line.strip():
                            continue
                        msg = json.loads(line)
                        if msg.get("status") == "unread":
                            unread += 1
                        latest = msg
                except Exception:
                    pass
            mailboxes.append({
                "agent_id": agent_dir.name,
                "name": agent_names.get(agent_dir.name, agent_dir.name),
                "unread": unread,
                "latest": latest,
            })
    
    existing = {m["agent_id"] for m in mailboxes}
    for agent_id, name in agent_names.items():
        if agent_id not in existing:
            mailboxes.append({
                "agent_id": agent_id,
                "name": name,
                "unread": 0,
                "latest": None,
            })
    
    return {"mailboxes": mailboxes}


@router.get("/api/mailbox/{agent_id}")
def get_mailbox(agent_id: str):
    """Get messages for a specific agent."""
    inbox_path = BASE_DIR / "agents" / "mailbox" / agent_id / "inbox.jsonl"
    if not inbox_path.exists():
        return {"messages": []}
    messages = []
    try:
        for line in inbox_path.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if line:
                messages.append(json.loads(line))
    except Exception:
        pass
    return {"messages": messages}


@router.post("/api/mailbox/{agent_id}")
def send_to_mailbox(agent_id: str, body: dict):
    """Admin sends a message to an agent's mailbox."""
    content = body.get("content", "").strip()
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)
    
    mailbox_dir = BASE_DIR / "agents" / "mailbox" / agent_id
    mailbox_dir.mkdir(parents=True, exist_ok=True)
    inbox_path = mailbox_dir / "inbox.jsonl"
    
    entry = {
        "from": "admin",
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "status": "unread",
    }
    with open(inbox_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    return {"status": "sent", "agent_id": agent_id}


@router.post("/api/mailbox/{agent_id}/read")
def mark_mailbox_read(agent_id: str):
    """Mark all messages as read for an agent."""
    inbox_path = BASE_DIR / "agents" / "mailbox" / agent_id / "inbox.jsonl"
    if not inbox_path.exists():
        return {"status": "ok"}
    try:
        messages = []
        for line in inbox_path.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if line:
                msg = json.loads(line)
                msg["status"] = "read"
                messages.append(msg)
        inbox_path.write_text(
            "\n".join(json.dumps(m, ensure_ascii=False) for m in messages) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    return {"status": "ok"}
