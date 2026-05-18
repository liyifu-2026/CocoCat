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


class KbChatRequest(BaseModel):
    content: str
    kb_name: str
    user_id: str = "local"
    session_id: str | None = None


# ── Routes ─────────────────────────────────────────────────


@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    """Send a message to Main AI via SandboxProvider."""
    msg_uuid = new_uuid()
    msg_store = ctx.db.messages
    msg_store.save(
        msg_uuid=msg_uuid, agent_id="main", user_id=body.user_id,
        role="user", content=body.content, scene_id=body.scene_id,
        channel_type="web",
    )

    sandbox_provider = ctx.sandbox_provider
    if not sandbox_provider:
        reply_uuid = new_uuid()
        msg_store.save(
            msg_uuid=reply_uuid, agent_id="main", user_id=body.user_id,
            role="assistant",
            content=f"[System] SandboxProvider not available. Received: {body.content[:200]}",
            scene_id=body.scene_id,
        )
        return {"reply": "SandboxProvider not available", "msg_uuid": reply_uuid}

    try:
        async def on_event(event_type: str, data: dict):
            await ctx.ws_manager.broadcast(event_type, {
                **(data or {}),
                "agent_id": "main",
                "session_id": body.session_id,
            })

        from cococat.core.tools import create_main_ai_tools

        sub_executor = ctx.sub_executor
        main_ai_tools = create_main_ai_tools(
            sub_agent_executor=sub_executor.dispatch if sub_executor else None,
            dag_store=ctx.dag_store,
        )

        reply = await sandbox_provider.run_once(
            prompt=body.content,
            agent_id="main",
            tools=main_ai_tools,
            on_event=on_event,
            session_id=body.session_id,
        )
    except Exception as e:
        reply = f"Error: {e}"

    reply_uuid = new_uuid()
    msg_store.save(
        msg_uuid=reply_uuid, agent_id="main", user_id=body.user_id,
        role="assistant", content=reply, scene_id=body.scene_id,
    )
    return {"reply": reply, "msg_uuid": reply_uuid}


@router.post("/kb-chat")
async def kb_chat(body: KbChatRequest, ctx: AppContext = Depends(get_ctx)):
    """Send a message to kb-agent via sandbox (same pattern as Coco)."""
    msg_uuid = new_uuid()
    msg_store = ctx.db.messages
    msg_store.save(
        msg_uuid=msg_uuid, agent_id="kb-agent", user_id=body.user_id,
        role="user", content=f"[KB:{body.kb_name}] {body.content}",
        scene_id="knowledge", channel_type="web",
    )

    sandbox_provider = ctx.sandbox_provider
    if not sandbox_provider:
        reply = "kb-agent sandbox not available"
        reply_uuid = new_uuid()
        msg_store.save(msg_uuid=reply_uuid, agent_id="kb-agent", user_id=body.user_id,
                       role="assistant", content=reply, scene_id="knowledge")
        return {"reply": reply, "msg_uuid": reply_uuid}

    from cococat.core.tools import create_resident_tools
    sub_executor = ctx.sub_executor
    kb_tools = create_resident_tools(
        sub_agent_executor=sub_executor.dispatch if sub_executor else None,
        dag_store=ctx.dag_store,
        is_kb_agent=True,
    )

    ws = ctx.ws_manager
    async def on_event(event_type: str, data: dict):
        await ws.broadcast(event_type, {
            **(data or {}),
            "agent_id": "kb-agent",
            "session_id": body.session_id,
        })

    try:
        reply = await sandbox_provider.run_once(
            prompt=f"[KB: {body.kb_name}] {body.content}",
            agent_id="kb-agent",
            tools=kb_tools,
            on_event=on_event,
            session_id=body.session_id,
        )
    except Exception as e:
        import traceback, logging
        logger = logging.getLogger("cococat.routes.chat")
        logger.error("kb-chat error: %s\n%s", e, traceback.format_exc())
        reply = f"Error: {e}"

    reply_uuid = new_uuid()
    msg_store.save(
        msg_uuid=reply_uuid, agent_id="kb-agent", user_id=body.user_id,
        role="assistant", content=reply, scene_id="knowledge",
    )
    return {"reply": reply, "msg_uuid": reply_uuid}


@router.get("/kb-chat/history")
async def kb_chat_history(ctx: AppContext = Depends(get_ctx), session_id: str = ""):
    """Get kb-chat session history."""
    import os, json
    path = os.path.join("agents", "kb-agent", "sessions", f"{session_id}.jsonl") if session_id else os.path.join("agents", "kb-agent", "session.jsonl")
    if not os.path.exists(path):
        return {"messages": []}
    messages = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    msg = json.loads(line)
                    messages.append({"role": msg.get("role", ""), "content": msg.get("content", "")})
                except json.JSONDecodeError:
                    pass
    return {"messages": messages}


@router.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str, ctx: AppContext = Depends(get_ctx)):
    """Delete a chat session and all associated records (DAG runs, sub-agent dirs, session files)."""
    import os, shutil
    deleted = {"dag_runs": 0, "session_files": 0, "sub_agent_dirs": 0}

    # 1. Delete DAG runs for this session
    store = ctx.dag_store
    if store:
        for run in store.list_all():
            if run.get("session_id") == session_id:
                store.delete(run.get("run_id", ""))
                deleted["dag_runs"] += 1

    # 2. Delete main agent session file
    for agent_id in ["main", "kb-agent"]:
        session_path = os.path.join("agents", agent_id, "sessions", f"{session_id}.jsonl")
        if os.path.exists(session_path):
            os.remove(session_path)
            deleted["session_files"] += 1
        # Also delete the default session file if it exists
        default_path = os.path.join("agents", agent_id, "session.jsonl")
        if os.path.exists(default_path):
            os.remove(default_path)
            deleted["session_files"] += 1

    # 3. Delete sub-agent session dirs
    agents_dir = "agents"
    if os.path.isdir(agents_dir):
        for name in os.listdir(agents_dir):
            if name.startswith("sub-"):
                path = os.path.join(agents_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    deleted["sub_agent_dirs"] += 1

    return {"status": "deleted", **deleted}


@router.get("/chat/history")
async def chat_history(ctx: AppContext = Depends(get_ctx), scene_id: str = "default", limit: int = 50, session_id: str = ""):
    """Get chat history. If session_id provided, reads from session file."""
    if session_id:
        import os, json as _json
        path = os.path.join("agents", "main", "sessions", f"{session_id}.jsonl")
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
    return {"messages": ctx.db.messages.get_chat_history(scene_id, limit)}
