"""Agent management routes.

TODO: Migrate all endpoints to proxy through Rust HTTP API:
  - GET /api/agents → Rust GET /api/agents
  - GET /api/agents/{id} → Rust GET /api/agents/{id}
  - PATCH /api/agents/{id} → Rust PATCH /api/agents/{id}
  - DELETE /api/agents/{id} → Rust DELETE /api/agents/{id}
  - Profile, skills, memory, display, entries → Rust equivalents
"""
from fastapi import APIRouter, Request
import json, os, sys
import httpx
from fastapi.responses import JSONResponse
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent

RUST_API = "http://localhost:3000/api/agents"


async def _proxy(method: str, path: str, request: Request, body: dict | None = None):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{RUST_API}{path}"
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth
            resp = await client.request(method, url, json=body, headers=headers, timeout=30)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)


@router.get("/api/agents")
async def list_agents(request: Request):
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth:
                headers["Authorization"] = auth
            resp = await client.get("http://localhost:3000/api/agents", headers=headers, timeout=30)
            data = resp.json()
            return JSONResponse(content={"agents": data} if isinstance(data, list) else data, status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)


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
async def get_agent(request: Request, agent_id: str):
    return await _proxy("GET", f"/{agent_id}", request)


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
async def update_agent(request: Request, agent_id: str, body: dict):
    return await _proxy("PATCH", f"/{agent_id}", request, body)


@router.patch("/api/agents/{agent_id}/skills")
def update_agent_skills(agent_id: str, body: dict):
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
async def delete_agent(request: Request, agent_id: str):
    return await _proxy("DELETE", f"/{agent_id}", request)


@router.get("/api/agents/{agent_id}/entries")
def get_agent_entries(agent_id: str):
    entries_path = BASE_DIR / "agents" / agent_id / "entries.json"
    if not entries_path.exists():
        return {"entries": []}
    try:
        return json.loads(entries_path.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": []}


@router.put("/api/agents/{agent_id}/entries")
def update_agent_entries(agent_id: str, body: dict):
    entries_path = BASE_DIR / "agents" / agent_id / "entries.json"
    entries = body.get("entries", [])
    entries_path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "updated", "entries": entries}


@router.get("/api/agents/{agent_id}/display")
def get_agent_display(agent_id: str):
    display_path = BASE_DIR / "agents" / agent_id / "display.json"
    display = {"nickname": "", "avatar": "", "color": "", "gender": ""}
    if display_path.exists():
        try:
            display.update(json.loads(display_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    profile_path = BASE_DIR / "agents" / agent_id / "profile.json"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            display["gender"] = profile.get("gender", "")
        except Exception:
            pass

    return display


@router.get("/api/agents/{agent_id}/memory/history")
def get_memory_history(agent_id: str, limit: int = 10):
    mem_dir = BASE_DIR / "agents" / agent_id / "memory"
    if not mem_dir.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "agent not found"}, status_code=404)
    sys.path.insert(0, str(BASE_DIR / "py-agent"))
    from git_store import GitStore
    store = GitStore(str(mem_dir))
    log = store.log(max_count=limit)
    return {"agent_id": agent_id, "history": log}


@router.get("/api/agents/{agent_id}/memory/users/{user_id}")
def get_user_memory(agent_id: str, user_id: str):
    mem_dir = BASE_DIR / "agents" / agent_id / "memory"
    if not mem_dir.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "agent not found"}, status_code=404)
    sys.path.insert(0, str(BASE_DIR / "py-agent"))
    from dream import get_user_memory_dir, _user_hash
    user_hash = _user_hash(user_id)
    user_dir = Path(get_user_memory_dir(agent_id, user_hash))
    profile_path = user_dir / "PROFILE.md"
    history_path = user_dir / "history.jsonl"
    profile = profile_path.read_text(encoding="utf-8") if profile_path.exists() else ""
    history = []
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return {
        "user_id": user_id, "user_hash": user_hash,
        "profile": profile, "history_count": len(history),
        "history": history[-20:],
    }


@router.put("/api/agents/{agent_id}/display")
def update_agent_display(agent_id: str, body: dict):
    display_path = BASE_DIR / "agents" / agent_id / "display.json"
    existing = {}
    if display_path.exists():
        try:
            existing = json.loads(display_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if "nickname" in body and existing.get("nickname"):
        return JSONResponse({"error": "Nickname is locked after first set"}, status_code=409)
    for key in ("nickname", "avatar", "color", "gender"):
        if key in body:
            existing[key] = body[key]
    display_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "updated", "display": existing}
