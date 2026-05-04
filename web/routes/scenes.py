"""Scene management routes.

TODO: Migrate all endpoints to proxy through Rust HTTP API:
  - POST /api/scenes → Rust POST /api/scenes
  - DELETE /api/scenes/{id} → Rust DELETE /api/scenes/{id}
  - PATCH /api/scenes/{id}/context → Rust PATCH /api/scenes/{id}/context
  - PATCH /api/scenes/{id}/kbs → Rust PATCH /api/scenes/{id}/kbs
  - PATCH /api/scenes/{id}/roster → Rust PATCH /api/scenes/{id}/roster
  - PATCH /api/scenes/{id}/skills → Rust PATCH /api/scenes/{id}/skills
"""
import json
import shutil
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent


@router.post("/api/scenes")
def create_scene(body: dict):
    """Create a new scene."""
    scene_id = body.get("id", "").strip()
    if not scene_id:
        return JSONResponse({"error": "scene id is required"}, status_code=400)

    scene_dir = BASE_DIR / "scenes" / scene_id
    if scene_dir.exists():
        return JSONResponse({"error": "scene already exists"}, status_code=409)

    scene_dir.mkdir(parents=True)
    context = body.get("context", f"# {scene_id}\n\nWork environment for {scene_id}.")
    (scene_dir / "CONTEXT.md").write_text(context, encoding="utf-8")
    (scene_dir / "mounted_kbs.json").write_text(
        json.dumps({"mounted": [], "search_mode": "token"}, indent=2), encoding="utf-8")
    (scene_dir / "roster.json").write_text(
        json.dumps({"agents": []}, indent=2), encoding="utf-8")

    skills_dir = scene_dir / "skills"
    skills_dir.mkdir()
    (skills_dir / "manifest.json").write_text(
        json.dumps({"env_skills": []}, indent=2), encoding="utf-8")

    return {"status": "created", "scene_id": scene_id}


@router.delete("/api/scenes/{scene_id}")
def delete_scene(scene_id: str):
    """Delete a scene and its directory."""
    scene_dir = BASE_DIR / "scenes" / scene_id
    if not scene_dir.exists():
        return JSONResponse({"error": "scene not found"}, status_code=404)
    shutil.rmtree(scene_dir)
    return {"status": "deleted", "scene_id": scene_id}


@router.patch("/api/scenes/{scene_id}/context")
def update_scene_context(scene_id: str, body: dict):
    """Update CONTEXT.md."""
    scene_dir = BASE_DIR / "scenes" / scene_id
    if not scene_dir.exists():
        return JSONResponse({"error": "scene not found"}, status_code=404)
    context = body.get("context", "")
    (scene_dir / "CONTEXT.md").write_text(context, encoding="utf-8")
    return {"status": "updated", "scene_id": scene_id}


@router.patch("/api/scenes/{scene_id}/kbs")
def update_scene_kbs(scene_id: str, body: dict):
    """Update mounted knowledge bases."""
    scene_dir = BASE_DIR / "scenes" / scene_id
    if not scene_dir.exists():
        return JSONResponse({"error": "scene not found"}, status_code=404)
    mount_path = scene_dir / "mounted_kbs.json"
    current = json.loads(mount_path.read_text(encoding="utf-8")) if mount_path.exists() else {"mounted": [], "search_mode": "token"}
    current["mounted"] = body.get("mounted", [])
    mount_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return {"status": "updated", "mounted": current["mounted"]}


@router.patch("/api/scenes/{scene_id}/roster")
def update_scene_roster(scene_id: str, body: dict):
    """Update agent roster."""
    scene_dir = BASE_DIR / "scenes" / scene_id
    if not scene_dir.exists():
        return JSONResponse({"error": "scene not found"}, status_code=404)
    roster_path = scene_dir / "roster.json"
    roster = {"agents": body.get("agents", [])}
    roster_path.write_text(json.dumps(roster, indent=2), encoding="utf-8")
    return {"status": "updated", "agents": roster["agents"]}


@router.patch("/api/scenes/{scene_id}/skills")
def update_scene_skills(scene_id: str, body: dict):
    """Update environment skills."""
    scene_dir = BASE_DIR / "scenes" / scene_id
    if not scene_dir.exists():
        return JSONResponse({"error": "scene not found"}, status_code=404)
    skills_dir = scene_dir / "skills"
    skills_dir.mkdir(exist_ok=True)
    manifest_path = skills_dir / "manifest.json"
    manifest = {"env_skills": body.get("env_skills", [])}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"status": "updated", "env_skills": manifest["env_skills"]}
