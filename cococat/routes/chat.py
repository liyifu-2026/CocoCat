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


# ── shared sandbox chat runner ──────────────────────────────

async def _run_sandbox_chat(
    ctx: AppContext,
    agent_id: str,
    prompt: str,
    session_id: str | None,
    tools: list,
) -> str:
    """Execute a chat prompt through ExecutorProvider with WebSocket event broadcast."""
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
    )


def _build_chat_tools(ctx: AppContext, preset: str) -> list:
    """Construct tool list for a given preset ('main_ai' or 'resident_kb')."""
    from cococat.core.tools import ToolCatalog, resolve_tavily_key

    sub_executor = ctx.sub_executor
    tavily_key = resolve_tavily_key(ctx.config_store)
    catalog = ToolCatalog(
        sub_agent_executor=sub_executor.dispatch if sub_executor else None,
        dag_store=ctx.dag_store,
        tavily_api_key=tavily_key,
    )
    if preset == "main_ai":
        return catalog.main_ai()
    return catalog.resident(kb_agent=True)


# ── Routes ─────────────────────────────────────────────────


@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    """Send a message to Main AI via ExecutorProvider."""
    user_id = ctx.user_id or body.user_id or "local"
    msg_uuid = new_uuid()
    msg_store = ctx.db.messages
    msg_store.save(
        msg_uuid=msg_uuid, agent_id="main", user_id=user_id,
        role="user", content=body.content, scene_id=body.scene_id,
        channel_type="web",
    )

    try:
        tools = _build_chat_tools(ctx, "main_ai")
        reply = await _run_sandbox_chat(ctx, "main", body.content, body.session_id, tools)
    except Exception as e:
        reply = f"Error: {e}"

    reply_uuid = new_uuid()
    msg_store.save(
        msg_uuid=reply_uuid, agent_id="main", user_id=user_id,
        role="assistant", content=reply, scene_id=body.scene_id,
    )
    return {"reply": reply, "msg_uuid": reply_uuid}


@router.post("/kb-chat")
async def kb_chat(body: KbChatRequest, ctx: AppContext = Depends(get_ctx)):
    """Send a message to kb-agent via sandbox (same pattern as Coco)."""
    msg_uuid = new_uuid()
    msg_store = ctx.db.messages
    prompt = f"[KB: {body.kb_name}] {body.content}"
    msg_store.save(
        msg_uuid=msg_uuid, agent_id="kb-agent", user_id=body.user_id,
        role="user", content=prompt,
        scene_id="knowledge", channel_type="web",
    )

    try:
        tools = _build_chat_tools(ctx, "resident_kb")
        reply = await _run_sandbox_chat(ctx, "kb-agent", prompt, body.session_id, tools)
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
    path = str(ctx.config_store.agents_dir / "kb-agent" / "sessions" / f"{session_id}.jsonl") if session_id else str(ctx.config_store.agents_dir / "kb-agent" / "session.jsonl")
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
        session_path = str(ctx.config_store.agents_dir / agent_id / "sessions" / f"{session_id}.jsonl")
        if os.path.exists(session_path):
            os.remove(session_path)
            deleted["session_files"] += 1
        # Also delete the default session file if it exists
        default_path = str(ctx.config_store.agents_dir / agent_id / "session.jsonl")
        if os.path.exists(default_path):
            os.remove(default_path)
            deleted["session_files"] += 1

    # 3. Delete sub-agent session dirs
    agents_dir = str(ctx.config_store.agents_dir)
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
        user = ctx.user_id or "main"
        path = os.path.join("agents", user, "sessions", f"{session_id}.jsonl")
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
