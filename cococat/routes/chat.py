"""Chat routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cococat.db import new_uuid
from cococat.app import get_ctx
from cococat.context import AppContext

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    content: str
    user_id: str = "local"
    scene_id: str = "default"
    session_id: str | None = None
    mode: str = "default"


# ── shared sandbox chat runner ──────────────────────────────

async def _run_sandbox_chat(
    ctx: AppContext,
    agent_id: str,
    prompt: str,
    session_id: str | None,
    tools: list,
    mode: str = "default",
    scene_id: str = "default",
    user_id: str = "local",
) -> str:
    sandbox_provider = ctx.sandbox_provider
    if not sandbox_provider:
        return f"[System] ExecutorProvider not available for agent '{agent_id}'"

    async def on_event(event_type: str, data: dict):
        await ctx.ws_manager.broadcast(event_type, {
            **(data or {}),
            "agent_id": agent_id,
            "session_id": session_id,
        })

    return await sandbox_provider.run_once(
        prompt=prompt,
        agent_id=agent_id,
        tools=tools,
        on_event=on_event,
        session_id=session_id,
        mode=mode,
        scene_id=scene_id,
        user_id=user_id,
    )


# ── Routes ─────────────────────────────────────────────────


@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    user_id = ctx.user_id or body.user_id or "local"
    msg_uuid = new_uuid()
    msg_store = ctx.db.messages
    msg_store.save(
        msg_uuid=msg_uuid, agent_id="main", user_id=user_id,
        role="user", content=body.content, scene_id=body.scene_id,
        channel_type="web",
    )

    from cococat.core.tools import resolve_tools_for_mode, resolve_tavily_key
    sub_executor = ctx.sub_executor
    tavily_key = resolve_tavily_key(ctx.config_store)
    tools = resolve_tools_for_mode(
        body.mode,
        sub_agent_executor=sub_executor.dispatch if sub_executor else None,
        tavily_api_key=tavily_key,
    )

    try:
        reply = await _run_sandbox_chat(ctx, "main", body.content, body.session_id, tools, mode=body.mode, scene_id=body.scene_id, user_id=user_id)
    except Exception as e:
        reply = f"Error: {e}"

    reply_uuid = new_uuid()
    msg_store.save(
        msg_uuid=reply_uuid, agent_id="main", user_id=user_id,
        role="assistant", content=reply, scene_id=body.scene_id,
    )
    return {"reply": reply, "msg_uuid": reply_uuid}


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
    """Get chat history. If session_id provided, reads from session file."""
    if session_id:
        import os, json as _json
        user = ctx.user_id or "local"
        path = os.path.join("scenes", scene_id, "sessions", user, f"{session_id}.jsonl")
        if not os.path.exists(path):
            return {"messages": []}
        msgs = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        msg = _json.loads(line)
                        msgs.append({"role": msg.get("role", ""), "content": msg.get("content", "")})
                    except _json.JSONDecodeError:
                        pass
        return {"messages": msgs}
    return {"messages": ctx.db.messages.get_chat_history(scene_id, limit, user_id=ctx.user_id)}
