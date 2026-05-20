"""Agent routes."""
import json
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext
from cococat.core.modes import load_mode

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    id: str
    name: str
    role: str = "sub"
    model: str = "deepseek-chat"


class AgentUpdate(BaseModel):
    name: str | None = None
    model: str | None = None


class SavePromptRequest(BaseModel):
    prompt: str


class WorkerConfigRequest(BaseModel):
    model: str


@router.get("")
async def list_agents(ctx: AppContext = Depends(get_ctx)):
    return {"agents": ctx.db.agents.list_all()}


@router.post("")
async def create_agent(body: AgentCreate, ctx: AppContext = Depends(get_ctx)):
    ctx.db.agents.create(body.id, body.name, body.role, body.model)
    return {"status": "created", "id": body.id}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, ctx: AppContext = Depends(get_ctx)):
    agent = ctx.db.agents.get(agent_id)
    if not agent:
        return {"error": "not found"}, 404
    return agent


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate, ctx: AppContext = Depends(get_ctx)):
    if body.name:
        ctx.db.agents.update_name(agent_id, body.name)
    if body.model:
        ctx.db.agents.update_model(agent_id, body.model)
        agent = ctx.pool.get_agent(agent_id)
        if agent and ctx.provider_factory:
            try:
                new_llm = ctx.provider_factory.create_sync(body.model)
                if new_llm:
                    agent._llm = new_llm
                    agent._system_prompt = agent._default_system_prompt
            except Exception:
                pass
    return {"status": "updated"}


# ── Coco system prompt ──

def _read_coco_prompt(store=None) -> str | None:
    if store is not None:
        return store.get_coco_prompt()
    return None


def _get_default_coco_prompt() -> str:
    return load_mode("default").system_prompt


def _get_effective_coco_prompt(store=None) -> str:
    custom = _read_coco_prompt(store)
    return custom or _get_default_coco_prompt()


@router.get("/main/prompt")
async def get_main_prompt(ctx: AppContext = Depends(get_ctx)):
    """Get Coco's current system prompt (custom or default)."""
    custom = _read_coco_prompt(ctx.config_store)
    return {
        "prompt": _get_effective_coco_prompt(ctx.config_store),
        "is_custom": custom is not None,
        "default": _get_default_coco_prompt(),
    }


@router.put("/main/prompt")
async def save_main_prompt(req: SavePromptRequest, ctx: AppContext = Depends(get_ctx)):
    """Save a custom system prompt for Coco."""
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt cannot be empty")
    if ctx.config_store:
        ctx.config_store.save_coco_prompt(prompt)
    _update_running_coco_prompt()
    return {"saved": True}


@router.delete("/main/prompt")
async def reset_main_prompt(ctx: AppContext = Depends(get_ctx)):
    """Reset Coco's system prompt to default."""
    if ctx.config_store:
        ctx.config_store.delete_coco_prompt()
    _update_running_coco_prompt()
    return {"reset": True}


def _update_running_coco_prompt() -> None:
    """Hot-reload Coco's system prompt from Mode YAML on next request."""
    pass


# ── Worker default config ──

def _worker_config_path() -> str:
    return os.environ.get("COCOCAT_CONFIG_FILE", "config/defaults.json")


def _load_worker_config(store=None) -> dict:
    if store is not None:
        return store.get_default() or {}
    return {}


def _save_worker_config(config: dict, store=None) -> None:
    if store is not None:
        store.save_defaults(config)
        return
    path = _worker_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


@router.get("/config")
async def get_agent_config(ctx: AppContext = Depends(get_ctx)):
    """Get global agent config (worker default model, etc.)."""
    config = _load_worker_config(ctx.config_store)
    return {
        "worker_model": config.get("worker_model", "deepseek-chat"),
    }


@router.put("/config")
async def save_agent_config(req: WorkerConfigRequest, ctx: AppContext = Depends(get_ctx)):
    """Save worker default model."""
    config = _load_worker_config(ctx.config_store)
    config["worker_model"] = req.model
    _save_worker_config(config, ctx.config_store)
    return {"saved": True}
