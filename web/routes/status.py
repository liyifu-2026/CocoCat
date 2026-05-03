"""Agent status tracking (idle/busy)."""
import time
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Simple in-memory status store
# In production, this would use Redis or a DB
_agent_status: dict[str, dict] = {}  # agent_id -> {"status": "idle"|"busy", "updated_at": timestamp}


@router.get("/api/agents/{agent_id}/status")
def get_agent_status(agent_id: str):
    """Get agent's current status (idle/busy)."""
    status = _agent_status.get(agent_id)
    if not status:
        return {"status": "idle", "agent_id": agent_id}
    return {"status": status["status"], "agent_id": agent_id}


@router.post("/api/agents/{agent_id}/status")
def update_agent_status(agent_id: str, body: dict):
    """Update agent's status (called by agent runtime)."""
    new_status = body.get("status", "idle")
    _agent_status[agent_id] = {"status": new_status, "updated_at": time.time()}
    return {"status": new_status}


@router.get("/api/agents/status")
def list_all_agent_status():
    """Get status for all agents."""
    return {"agents": _agent_status}
