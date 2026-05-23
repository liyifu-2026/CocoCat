"""Chat routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext
from cococat.core.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    content: str
    user_id: str = "local"
    scene_id: str = "default"
    session_id: str | None = None
    mode: str = "default"


@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    user_id = ctx.user_id or body.user_id or "local"
    service = ChatService(ctx)
    return await service.chat(
        body.content,
        user_id=user_id,
        scene_id=body.scene_id,
        session_id=body.session_id,
        mode=body.mode,
    )


@router.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str, ctx: AppContext = Depends(get_ctx)):
    import os, shutil
    deleted = {"session_files": 0, "sub_agent_dirs": 0}

    scenes_dir = "scenes"
    if os.path.isdir(scenes_dir):
        for scene_name in os.listdir(scenes_dir):
            sessions_dir = os.path.join(scenes_dir, scene_name, "sessions")
            if not os.path.isdir(sessions_dir):
                continue
            for user_dir in os.listdir(sessions_dir):
                session_path = os.path.join(sessions_dir, user_dir, f"{session_id}.jsonl")
                if os.path.exists(session_path):
                    os.remove(session_path)
                    deleted["session_files"] += 1

    agents_dir = str(ctx.config_store.agents_dir)
    if os.path.isdir(agents_dir):
        for name in os.listdir(agents_dir):
            if name.startswith("sub-"):
                path = os.path.join(agents_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    deleted["sub_agent_dirs"] += 1

    return {"status": "deleted", **deleted}


@router.get("/modes")
async def list_modes_route():
    from cococat.core.modes import list_modes
    modes = list_modes()
    return [
        {"id": m.id, "name": m.name, "description": m.description}
        for m in modes
    ]


@router.get("/chat/history")
async def chat_history(ctx: AppContext = Depends(get_ctx), scene_id: str = "default", limit: int = 50, session_id: str = ""):
    service = ChatService(ctx)
    return await service.get_history(scene_id=scene_id, limit=limit, session_id=session_id)
