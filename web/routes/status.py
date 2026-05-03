"""Agent status tracking + health monitoring."""
import os
import sys
from pathlib import Path
from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "py-agent"))
from agent_status import get_status, list_all, detect_stale, set_status_file

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
set_status_file(str(BASE_DIR / "agents" / "_status.json"))


@router.get("/api/agents/{agent_id}/status")
def get_agent_status(agent_id: str):
    return get_status(agent_id)


@router.post("/api/agents/{agent_id}/status")
def update_agent_status(agent_id: str, body: dict):
    from agent_status import report
    report(agent_id, body.get("status", "idle"), body.get("detail", ""))
    return {"status": body.get("status", "idle")}


@router.get("/api/agents/status")
def list_all_agent_status():
    return {"agents": list_all()}


@router.get("/api/health")
def system_health():
    """Full system health check."""
    config_path = BASE_DIR / "agents" / "config.toml"
    expected = 0
    if config_path.exists():
        try:
            import tomllib
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            expected = len([a for a in config.get("agents", []) if a.get("enabled", True)])
        except Exception:
            pass
    stale = detect_stale(300)
    return {
        "status": "ok",
        "agents_expected": expected,
        "agents_status": list_all(),
        "stale_agents": stale,
    }
