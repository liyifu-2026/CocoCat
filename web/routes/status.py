"""Agent status tracking + health monitoring."""
import os
import time
import subprocess
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent

_agent_status: dict[str, dict] = {}


def _find_agent_pids() -> dict[str, int]:
    """Find agent_runtime.py processes by scanning running processes."""
    pids = {}
    try:
        if os.name == "nt":
            output = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq python.exe"],
                text=True, timeout=10,
            )
            for line in output.strip().split("\n"):
                if "agent_runtime" in line:
                    parts = line.strip('"').split('","')
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1])
                            name = "unknown"
                            pids[name] = pid
                        except ValueError:
                            pass
        else:
            output = subprocess.check_output(
                ["pgrep", "-f", "agent_runtime.py"], text=True, timeout=10,
            )
            for pid_str in output.strip().split("\n"):
                if pid_str.strip():
                    pids[f"pid_{pid_str}"] = int(pid_str.strip())
    except Exception:
        pass
    return pids


@router.get("/api/agents/{agent_id}/status")
def get_agent_status(agent_id: str):
    status = _agent_status.get(agent_id)
    if not status:
        return {"status": "idle", "agent_id": agent_id}
    return {"status": status["status"], "agent_id": agent_id}


@router.post("/api/agents/{agent_id}/status")
def update_agent_status(agent_id: str, body: dict):
    new_status = body.get("status", "idle")
    _agent_status[agent_id] = {"status": new_status, "updated_at": time.time()}
    return {"status": new_status}


@router.get("/api/agents/status")
def list_all_agent_status():
    return {"agents": _agent_status}


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
    live_pids = _find_agent_pids()
    return {
        "status": "ok",
        "agents_expected": expected,
        "agents_running": len(live_pids),
        "processes": list(live_pids.keys()),
        "memory_agents": list(_agent_status.keys()),
    }
