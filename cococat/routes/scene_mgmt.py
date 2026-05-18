"""Scene management endpoints — KB/Skills CRUD."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext

router = APIRouter(prefix="/api/scenes", tags=["scene-management"])


class KBUpdate(BaseModel):
    mounted: list[str]


class SkillsUpdate(BaseModel):
    skills: list[str]


@router.patch("/{scene_id}/kbs")
async def update_scene_kbs(scene_id: str, body: KBUpdate,
                           ctx: AppContext = Depends(get_ctx)):
    import json
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        return {"error": "not found"}, 404
    ctx.db.scenes.update(scene_id, {"kbs": json.dumps(body.mounted)})
    return {"id": scene_id, "kbs": body.mounted}


@router.patch("/{scene_id}/skills")
async def update_scene_skills(scene_id: str, body: SkillsUpdate,
                              ctx: AppContext = Depends(get_ctx)):
    import json
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        return {"error": "not found"}, 404
    ctx.db.scenes.update(scene_id, {"skills": json.dumps(body.skills)})
    return {"id": scene_id, "skills": body.skills}
