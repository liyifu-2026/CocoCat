"""Agent management routes."""
from fastapi import APIRouter
import json, os
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


@router.get("/api/agents")
def list_agents():
    config_path = BASE_DIR / "agents" / "config.toml"
    agents = []
    if config_path.exists():
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for a in data.get("agents", []):
            agents.append({
                "id": a["id"], "name": a["name"],
                "enabled": a.get("enabled", True), "scene": a.get("scene", "default"),
            })
    return {"agents": agents}


@router.get("/api/usage")
def get_usage(limit: int = 50):
    usage_path = BASE_DIR / "agents" / "_usage.jsonl"
    entries = []
    if usage_path.exists():
        with open(usage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except: pass
    return {"usage": entries[-limit:]}
