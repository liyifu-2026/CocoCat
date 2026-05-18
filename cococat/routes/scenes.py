"""Scene routes — reads from filesystem (scene.yaml) + DB fallback."""

import json

from fastapi import APIRouter, Depends, HTTPException
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


class SceneLifecycleAction(BaseModel):
    action: str


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


class SceneUpdateFull(BaseModel):
    name: str | None = None
    description: str | None = None
    context: str | None = None
    kbs: list[str] | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    channels: list[str] | None = None
    visibility: str | None = None
    agent_name: str | None = None
    agent_tone: str | None = None
    agent_language: str | None = None
    agent_model: str | None = None


@router.get("")
async def list_scenes(ctx: AppContext = Depends(get_ctx)):
    rows = ctx.db._conn.execute(
        "SELECT * FROM scenes WHERE status != 'deleted' ORDER BY created_at DESC"
    ).fetchall()
    scenes = []
    for row in rows:
        d = dict(row)
        for field in ("kbs", "skills", "tools", "channels"):
            try:
                d[field] = json.loads(d.get(field, "[]"))
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        try:
            d["llm_config"] = json.loads(d.get("llm_config", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["llm_config"] = {}
        scenes.append(d)
    return scenes


@router.post("")
async def create_scene(body: SceneCreate, ctx: AppContext = Depends(get_ctx)):
    ctx.db.scenes.create(body.id, body.name)
    return {"status": "created", "id": body.id}


@router.get("/{scene_id}")
async def get_scene(scene_id: str, ctx: AppContext = Depends(get_ctx)):
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    agent_id = scene.get("agent_id")
    if agent_id:
        agent = ctx.db.agents.get(agent_id)
        if agent:
            personality = ctx.db.agents.get_personality(agent_id)
            scene["agent"] = {
                "id": agent_id,
                "name": agent.get("name", ""),
                "model": agent.get("model", ""),
                "personality": personality.get("personality", ""),
                "tone": personality.get("tone", ""),
                "language": personality.get("language", ""),
            }
    return scene


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


@router.post("/{scene_id}/lifecycle", response_model=dict)
async def scene_lifecycle(scene_id: str, body: SceneLifecycleAction,
                          ctx: AppContext = Depends(get_ctx)):
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    status = scene.get("status", "running")
    action = body.action

    valid_transitions = {
        "running": {"pause", "archive", "delete"},
        "paused": {"resume", "archive", "delete"},
        "archived": {"resume", "delete"},
        "deleted": set(),
    }
    if action not in valid_transitions.get(status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot {action} a scene with status '{status}'"
        )

    status_map = {
        "resume": "running",
        "pause": "paused",
        "archive": "archived",
        "delete": "deleted",
    }
    new_status = status_map[action]

    ctx.db.scenes.set_status(scene_id, new_status)

    agent_id = scene.get("agent_id")
    if agent_id:
        if new_status in ("paused", "archived", "deleted"):
            ctx.db._conn.execute(
                "UPDATE agents SET status = 'stopped' WHERE id = ?", (agent_id,)
            )
        elif new_status == "running":
            ctx.db._conn.execute(
                "UPDATE agents SET status = 'running' WHERE id = ?", (agent_id,)
            )
        ctx.db._conn.commit()

    return {"id": scene_id, "status": new_status, "previous_status": status}


@router.patch("/{scene_id}", response_model=dict)
async def update_scene_full(scene_id: str, body: SceneUpdateFull,
                            ctx: AppContext = Depends(get_ctx)):
    scene = ctx.db.scenes.get_full(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    scene_updates = {}
    for field in ("name", "description", "context", "visibility"):
        val = getattr(body, field)
        if val is not None:
            scene_updates[field] = val
    for field in ("kbs", "skills", "tools", "channels"):
        val = getattr(body, field)
        if val is not None:
            scene_updates[field] = json.dumps(val)

    if scene_updates:
        ctx.db.scenes.update(scene_id, scene_updates)

    agent_id = scene.get("agent_id")
    if agent_id:
        agent_updates = {}
        if body.agent_name is not None:
            agent_updates["name"] = body.agent_name
        if body.agent_model is not None:
            agent_updates["model"] = body.agent_model
        if body.agent_tone is not None or body.agent_language is not None:
            row = ctx.db._conn.execute(
                "SELECT metadata FROM agents WHERE id = ?", (agent_id,)
            ).fetchone()
            existing_meta = json.loads(row["metadata"] if row else "{}")
            if body.agent_tone is not None:
                existing_meta["tone"] = body.agent_tone
            if body.agent_language is not None:
                existing_meta["language"] = body.agent_language
            agent_updates["metadata"] = json.dumps(existing_meta)

        if agent_updates:
            set_clauses = ", ".join(f"{k} = ?" for k in agent_updates)
            values = list(agent_updates.values()) + [agent_id]
            ctx.db._conn.execute(
                f"UPDATE agents SET {set_clauses} WHERE id = ?", values
            )
            ctx.db._conn.commit()

    return ctx.db.scenes.get_full(scene_id)
