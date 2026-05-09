"""Scene routes — reads from filesystem (scene.yaml) + DB fallback."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from cococat.scene.config import load_scene_config, list_scenes as list_fs_scenes

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


class SceneCreate(BaseModel):
    id: str
    name: str


class SceneUpdate(BaseModel):
    name: str | None = None
    context: str | None = None
    kbs: list[str] | None = None
    skills: list[str] | None = None


@router.get("")
async def list_scenes(request: Request):
    # Filesystem first, DB fallback
    fs_scenes = list_fs_scenes()
    if fs_scenes:
        return {
            "scenes": [
                {
                    "id": s.id, "name": s.name,
                    "kbs": s.kbs, "skills": s.skills,
                    "channels": s.channels,
                }
                for s in fs_scenes
            ]
        }

    db = request.app.state.db
    rows = db.execute("SELECT id, name, description, created_at FROM scenes")
    return {
        "scenes": [
            {"id": r[0], "name": r[1], "description": r[2], "created_at": r[3]}
            for r in rows
        ]
    }


@router.post("")
async def create_scene(body: SceneCreate, request: Request):
    db = request.app.state.db
    db.execute_insert(
        "INSERT INTO scenes (id, name) VALUES (?, ?)",
        (body.id, body.name),
    )
    return {"status": "created", "id": body.id}


@router.get("/{scene_id}")
async def get_scene(scene_id: str, request: Request):
    # Try filesystem first
    config = load_scene_config(scene_id)
    if config:
        return {
            "id": config.id, "name": config.name,
            "context": config.context, "roster": config.roster,
            "kbs": config.kbs, "skills": config.skills,
            "channels": config.channels,
        }

    # DB fallback
    db = request.app.state.db
    rows = db.execute(
        "SELECT id, name, description, roster FROM scenes WHERE id = ?",
        (scene_id,),
    )
    if not rows:
        return {"error": "not found"}, 404
    r = rows[0]
    return {"id": r[0], "name": r[1], "description": r[2], "roster": r[3]}


@router.delete("/{scene_id}")
async def delete_scene(scene_id: str, request: Request):
    db = request.app.state.db
    db.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
    db.commit()
    return {"status": "deleted"}
