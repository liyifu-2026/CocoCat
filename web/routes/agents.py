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


@router.patch("/api/agents/{agent_id}")
def update_agent(agent_id: str, body: dict):
    """Update agent config (name, scene, enabled)."""
    config_path = BASE_DIR / "agents" / "config.toml"
    if not config_path.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "config not found"}, status_code=404)

    import tomllib
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    found = False
    for a in data.get("agents", []):
        if a["id"] == agent_id:
            if "name" in body:
                a["name"] = body["name"]
            if "scene" in body:
                a["scene"] = body["scene"]
            if "enabled" in body:
                a["enabled"] = body["enabled"]
            found = True
            break

    if not found:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "agent not found"}, status_code=404)

    import tomli_w
    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    return {"status": "updated", "agent_id": agent_id}


@router.patch("/api/agents/{agent_id}/skills")
def update_agent_skills(agent_id: str, body: dict):
    """Replace agent's skill manifest."""
    skills_dir = BASE_DIR / "agents" / agent_id / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = skills_dir / "manifest.json"

    manifest = {
        "public": body.get("public", []),
        "private": body.get("private", []),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "updated", "agent_id": agent_id}


@router.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str):
    """Remove an agent's config entry and directory."""
    config_path = BASE_DIR / "agents" / "config.toml"
    import tomllib
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    agents = data.get("agents", [])
    new_agents = [a for a in agents if a["id"] != agent_id]
    if len(new_agents) == len(agents):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "agent not found"}, status_code=404)

    data["agents"] = new_agents
    import tomli_w
    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)

    agent_dir = BASE_DIR / "agents" / agent_id
    if agent_dir.exists():
        import shutil
        shutil.rmtree(agent_dir)

    return {"status": "deleted", "agent_id": agent_id}


@router.get("/api/agents/{agent_id}/entries")
def get_agent_entries(agent_id: str):
    """Get agent's personal entry configuration."""
    entries_path = BASE_DIR / "agents" / agent_id / "entries.json"
    if not entries_path.exists():
        return {"entries": []}
    try:
        return json.loads(entries_path.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": []}


@router.put("/api/agents/{agent_id}/entries")
def update_agent_entries(agent_id: str, body: dict):
    """Update agent's personal entry configuration."""
    entries_path = BASE_DIR / "agents" / agent_id / "entries.json"
    entries = body.get("entries", [])
    entries_path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "updated", "entries": entries}


@router.get("/api/agents/{agent_id}/display")
def get_agent_display(agent_id: str):
    """Get agent's display config with gender from profile."""
    display_path = BASE_DIR / "agents" / agent_id / "display.json"
    display = {"nickname": "", "avatar": "", "color": "", "gender": ""}
    if display_path.exists():
        try:
            display.update(json.loads(display_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    # Read gender from immutable profile.json
    profile_path = BASE_DIR / "agents" / agent_id / "profile.json"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            display["gender"] = profile.get("gender", "")
        except Exception:
            pass

    return display


@router.put("/api/agents/{agent_id}/display")
def update_agent_display(agent_id: str, body: dict):
    """Update agent's display config."""
    display_path = BASE_DIR / "agents" / agent_id / "display.json"
    config = {
        "nickname": body.get("nickname", ""),
        "avatar": body.get("avatar", ""),
        "color": body.get("color", ""),
    }
    display_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "updated", "display": config}
