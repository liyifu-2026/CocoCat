"""Agent routes."""
import json
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext
from cococat.prompt import STATIC_PREFIX

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
    return {"agents": ctx.db.list_agents()}


@router.post("")
async def create_agent(body: AgentCreate, ctx: AppContext = Depends(get_ctx)):
    ctx.db.create_agent(body.id, body.name, body.role, body.model)
    return {"status": "created", "id": body.id}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, ctx: AppContext = Depends(get_ctx)):
    agent = ctx.db.get_agent(agent_id)
    if not agent:
        return {"error": "not found"}, 404
    return agent


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate, ctx: AppContext = Depends(get_ctx)):
    if body.name:
        ctx.db.update_agent_name(agent_id, body.name)
    if body.model:
        ctx.db.update_agent_model(agent_id, body.model)
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

def _coco_prompt_path() -> str:
    return os.environ.get("COCOCAT_COCO_PROMPT", "config/prompts/coco.txt")


def _read_coco_prompt() -> str | None:
    path = _coco_prompt_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read().strip()
                return content if content else None
        except OSError:
            pass
    return None


def _get_effective_coco_prompt() -> str:
    custom = _read_coco_prompt()
    return custom or STATIC_PREFIX


@router.get("/main/prompt")
async def get_main_prompt():
    """Get Coco's current system prompt (custom or default)."""
    custom = _read_coco_prompt()
    return {
        "prompt": _get_effective_coco_prompt(),
        "is_custom": custom is not None,
        "default": STATIC_PREFIX,
    }


@router.put("/main/prompt")
async def save_main_prompt(req: SavePromptRequest):
    """Save a custom system prompt for Coco."""
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt cannot be empty")
    path = _coco_prompt_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(prompt)
    # Update running agent's prompt if available
    _update_running_coco_prompt(prompt)
    return {"saved": True}


@router.delete("/main/prompt")
async def reset_main_prompt():
    """Reset Coco's system prompt to default."""
    path = _coco_prompt_path()
    if os.path.exists(path):
        os.remove(path)
    _update_running_coco_prompt(STATIC_PREFIX)
    return {"reset": True}


def _update_running_coco_prompt(prompt: str) -> None:
    """Hot-reload Coco's system prompt if running."""
    try:
        import importlib
        from cococat import prompt as prompt_module
        importlib.reload(prompt_module)
    except Exception:
        pass


# ── Worker default config ──

def _worker_config_path() -> str:
    return os.environ.get("COCOCAT_CONFIG_FILE", "config/defaults.json")


def _load_worker_config() -> dict:
    path = _worker_config_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_worker_config(config: dict) -> None:
    path = _worker_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


@router.get("/config")
async def get_agent_config():
    """Get global agent config (worker default model, etc.)."""
    config = _load_worker_config()
    return {
        "worker_model": config.get("worker_model", "deepseek-chat"),
    }


@router.put("/config")
async def save_agent_config(req: WorkerConfigRequest):
    """Save worker default model."""
    config = _load_worker_config()
    config["worker_model"] = req.model
    _save_worker_config(config)
    return {"saved": True}
