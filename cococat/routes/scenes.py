"""Scene routes — reads from filesystem (scene.yaml) + DB fallback."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cococat.scene.config import load_scene_config, list_scenes as list_fs_scenes
from cococat.app import get_ctx
from cococat.context import AppContext

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
async def list_scenes(ctx: AppContext = Depends(get_ctx)):
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

    rows = ctx.db.list_scenes()
    return {"scenes": rows}


@router.post("")
async def create_scene(body: SceneCreate, ctx: AppContext = Depends(get_ctx)):
    ctx.db.create_scene(body.id, body.name)
    return {"status": "created", "id": body.id}


@router.get("/{scene_id}")
async def get_scene(scene_id: str, ctx: AppContext = Depends(get_ctx)):
    config = load_scene_config(scene_id)
    if config:
        return {
            "id": config.id, "name": config.name,
            "context": config.context, "roster": config.roster,
            "kbs": config.kbs, "skills": config.skills,
            "channels": config.channels,
        }

    row = ctx.db.get_scene(scene_id)
    if not row:
        return {"error": "not found"}, 404
    return row


@router.delete("/{scene_id}")
async def delete_scene(scene_id: str, ctx: AppContext = Depends(get_ctx)):
    ctx.db.delete_scene(scene_id)
    return {"status": "deleted"}
