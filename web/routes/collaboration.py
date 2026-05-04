"""Collaboration graph API — reads Rust message bus data and returns DAG structure.

TODO: Migrate to proxy through Rust HTTP API:
  - GET /api/collaboration/graph → Rust GET /api/collaboration/graph
  - GET /api/collaboration/graph/events → Rust GET /api/collaboration/graph/events
  - File reads (chat/group.jsonl, config.toml) → Rust SQLite
"""
import json
from pathlib import Path
from fastapi import APIRouter, Request

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@router.get("/api/collaboration/graph")
async def collaboration_graph(request: Request):
    chat_path = BASE_DIR / "chat" / "group.jsonl"
    if not chat_path.exists():
        return {"nodes": [], "edges": []}

    messages = []
    with open(chat_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    agent_ids = set()
    for m in messages:
        f = m.get("from", "")
        t = m.get("to", "")
        if f and f != "system":
            agent_ids.add(f)
        if t and t not in ("*", "system", ""):
            agent_ids.add(t)

    import tomllib
    config_path = BASE_DIR / "agents" / "config.toml"
    agent_names = {}
    if config_path.exists():
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        for a in config.get("agents", []):
            agent_names[a["id"]] = a.get("name", a["id"])

    nodes = [
        {"id": aid, "label": agent_names.get(aid, aid)}
        for aid in sorted(agent_ids)
    ]

    tasks = {}
    for m in messages:
        tid = m.get("task_id")
        if tid is None:
            continue
        if tid not in tasks:
            tasks[tid] = {"task": None, "replies": []}
        if m.get("message_type") == "task":
            tasks[tid]["task"] = m
        else:
            tasks[tid]["replies"].append(m)

    edges = []
    for tid, flow in tasks.items():
        task = flow["task"]
        if not task:
            continue
        edges.append({
            "id": f"task_{tid}",
            "from": task.get("from", ""),
            "to": task.get("to", ""),
            "task_id": tid,
            "type": task.get("message_type", "task"),
            "summary": (task.get("content", "") or "")[:100],
            "timestamp": task.get("timestamp", ""),
            "replies": [
                {
                    "from": r.get("from", ""),
                    "content": (r.get("content", "") or "")[:200],
                    "timestamp": r.get("timestamp", ""),
                }
                for r in flow["replies"]
            ],
        })

    return {"nodes": nodes, "edges": edges}


@router.get("/api/collaboration/graph/events")
async def recent_events(request: Request):
    chat_path = BASE_DIR / "chat" / "group.jsonl"
    if not chat_path.exists():
        return {"edges": []}

    import datetime
    cutoff = (datetime.datetime.now(datetime.timezone.utc) -
              datetime.timedelta(seconds=60)).isoformat()

    recent_edges = []
    with open(chat_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    m = json.loads(line)
                    if m.get("timestamp", "") >= cutoff and m.get("message_type") in ("task", "reply"):
                        recent_edges.append(m)
                except json.JSONDecodeError:
                    pass

    return {"edges": recent_edges[-20:]}
