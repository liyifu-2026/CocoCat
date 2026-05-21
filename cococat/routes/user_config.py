"""User Coco configuration routes — model, prompt, API keys."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext
from cococat.config_store import ConfigStore

router = APIRouter(prefix="/api/user", tags=["user-config"])


class UserConfigUpdate(BaseModel):
    model: str | None = None
    prompt: str | None = None
    provider: str | None = None
    api_key: str | None = None


@router.get("/config")
async def get_user_config(ctx: AppContext = Depends(get_ctx)):
    user_id = ctx.user_id or "local"
    store = ConfigStore(user_id=user_id)
    defaults = store.get_default() or {}
    auth = store.all_auth()
    prompt = store.get_coco_prompt() or ""
    return {
        "model": defaults.get("worker_model", ""),
        "prompt": prompt,
        "provider": list(auth.keys())[0] if auth else "",
        "api_key_set": bool(auth),
        "user_id": user_id,
    }


@router.post("/config")
async def update_user_config(body: UserConfigUpdate, ctx: AppContext = Depends(get_ctx)):
    user_id = ctx.user_id or "local"
    store = ConfigStore(user_id=user_id)
    defaults = store.get_default() or {}

    if body.model:
        defaults["worker_model"] = body.model
    store.save_defaults(defaults)

    if body.prompt is not None:
        if body.prompt.strip():
            store.save_coco_prompt(body.prompt.strip())
        else:
            store.delete_coco_prompt()

    if body.provider and body.api_key:
        store.set_auth(body.provider, body.api_key)

    return {"status": "saved"}
