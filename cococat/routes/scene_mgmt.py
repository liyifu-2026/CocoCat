"""Scene management endpoints — KB/Skills CRUD."""
from fastapi import APIRouter, Request
from pydantic import BaseModel
import os
import yaml

router = APIRouter(prefix="/api/scenes", tags=["scene-management"])


class KBUpdate(BaseModel):
    mounted: list[str]


class SkillsUpdate(BaseModel):
    skills: list[str]


def _read_scene_yaml(scene_id: str) -> dict:
    path = os.path.join("scenes", scene_id, "scene.yaml")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_scene_yaml(scene_id: str, data: dict) -> None:
    path = os.path.join("scenes", scene_id, "scene.yaml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


@router.patch("/{scene_id}/kbs")
async def update_scene_kbs(scene_id: str, body: KBUpdate, request: Request):
    """Mount/unmount KBs for a scene."""
    data = _read_scene_yaml(scene_id)
    if not data:
        data = {"id": scene_id, "name": scene_id}

    data["kbs"] = body.mounted
    _write_scene_yaml(scene_id, data)

    return {"status": "updated", "mounted": body.mounted}


@router.patch("/{scene_id}/skills")
async def update_scene_skills(scene_id: str, body: SkillsUpdate, request: Request):
    """Add/remove scene skills."""
    data = _read_scene_yaml(scene_id)
    if not data:
        data = {"id": scene_id, "name": scene_id}

    data["skills"] = body.skills
    _write_scene_yaml(scene_id, data)

    return {"status": "updated", "skills": body.skills}
