"""Scene routes — reads from filesystem (scene.yaml) + DB fallback."""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

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


class SceneCreateFull(BaseModel):
    id: str
    name: str
    description: str = ""
    purpose: str = ""
    agent_name: str = ""
    agent_tone: str = "friendly"
    agent_language: str = "zh"
    agent_model: str = ""
    kbs: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    visibility: str = "private"


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

    rows = ctx.db.scenes.list_all()
    return {"scenes": rows}


@router.post("")
async def create_scene(body: SceneCreate, ctx: AppContext = Depends(get_ctx)):
    ctx.db.scenes.create(body.id, body.name)
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

    row = ctx.db.scenes.get(scene_id)
    if not row:
        return {"error": "not found"}, 404
    return row


@router.delete("/{scene_id}")
async def delete_scene(scene_id: str, ctx: AppContext = Depends(get_ctx)):
    ctx.db.scenes.delete(scene_id)
    return {"status": "deleted"}


@router.post("/full", response_model=dict)
async def create_scene_full(body: SceneCreateFull, ctx: AppContext = Depends(get_ctx)):
    from cococat.scene.generator import generate_scene_config, AGENT_TONES

    gen = generate_scene_config(
        purpose=body.purpose,
        name=body.name,
        description=body.description,
        tone=body.agent_tone,
        language=body.agent_language,
        agent_name=body.agent_name or body.name,
        agent_model=body.agent_model or "",
    )

    agent_id = body.id
    agent_config = {
        "id": agent_id,
        "name": body.agent_name or body.name,
        "role": "resident",
        "model": body.agent_model or "",
        "scene_id": body.id,
        "status": "running",
        "system_prompt": gen["agent_system_prompt"],
        "personality": AGENT_TONES.get(body.agent_tone, ""),
        "tone": body.agent_tone,
        "language": body.agent_language,
    }
    ctx.db.agents.create_full(agent_config)

    scene_config = {
        "id": body.id,
        "name": body.name,
        "description": body.description,
        "context": gen["context"],
        "agent_id": agent_id,
        "status": "running",
        "purpose": body.purpose,
        "kbs": body.kbs,
        "skills": body.skills,
        "tools": body.tools,
        "channels": body.channels,
        "llm_config": {},
        "visibility": body.visibility,
    }
    ctx.db.scenes.create_full(scene_config)

    return ctx.db.scenes.get_full(body.id)
