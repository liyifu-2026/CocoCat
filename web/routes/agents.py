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


@router.get("/api/agents/{agent_id}")
def get_agent(agent_id: str):
    config_path = BASE_DIR / "agents" / "config.toml"
    if config_path.exists():
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        for a in data.get("agents", []):
            if a["id"] == agent_id:
                return {
                    "id": a["id"],
                    "name": a["name"],
                    "enabled": a.get("enabled", True),
                    "scene": a.get("scene", "default"),
                    "interpreter": a.get("interpreter", ""),
                    "script": a.get("script", ""),
                }
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": "agent not found"}, status_code=404)


@router.get("/api/agents/{agent_id}/profile")
def get_agent_profile(agent_id: str):
    profile_path = BASE_DIR / "agents" / agent_id / "profile.json"
    if not profile_path.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "profile not found"}, status_code=404)
    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/agents/{agent_id}/skills")
def get_agent_skills(agent_id: str):
    skills_path = BASE_DIR / "agents" / agent_id / "skills" / "manifest.json"
    if not skills_path.exists():
        return {"public": [], "private": []}
    try:
        return json.loads(skills_path.read_text(encoding="utf-8"))
    except Exception:
        return {"public": [], "private": []}


@router.get("/api/agents/{agent_id}/memory")
def get_agent_memory(agent_id: str):
    mem_path = BASE_DIR / "agents" / agent_id / "memory" / "MEMORY.md"
    if not mem_path.exists():
        return {"content": ""}
    return {"content": mem_path.read_text(encoding="utf-8")}


@router.get("/api/agents/{agent_id}/history")
def get_agent_history(agent_id: str, limit: int = 50):
    hist_path = BASE_DIR / "agents" / agent_id / "memory" / "history.jsonl"
    entries = []
    if hist_path.exists():
        for line in hist_path.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return {"entries": entries[-limit:]}
