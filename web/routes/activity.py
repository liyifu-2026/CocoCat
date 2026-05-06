"""Activity timeline API — aggregates agent activity logs."""
import json
from pathlib import Path
from fastapi import APIRouter, Query

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


@router.get("/api/activity")
def list_activity(limit: int = Query(50, ge=1, le=200)):
    """Return merged activity timeline across all agents, newest first."""
    agents_dir = BASE_DIR / "agents"
    if not agents_dir.exists():
        return {"activities": []}

    entries = []
    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        activity_file = agent_dir / "activity.jsonl"
        if not activity_file.exists():
            continue
        try:
            for line in activity_file.read_text(encoding="utf-8").strip().split("\n"):
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return {"activities": entries[:limit]}
