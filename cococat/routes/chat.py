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


# ── WebSocket streaming helpers ────────────────────────────

def _make_event_handler(ws):
    """Create on_event callback that broadcasts to WebSocket."""
    async def on_event(event_type: str, data: dict):
        await ws.broadcast(event_type, data)
    return on_event


def _make_stream_callbacks(ws, agent_id: str, session_id: str | None):
    """Create on_text/on_reasoning/on_tool callbacks for agent.run()."""

    async def on_text(delta: str):
        await ws.broadcast("text_delta", {
            "content": delta, "agent_id": agent_id, "session_id": session_id,
        })

    async def on_reasoning(content: str):
        await ws.broadcast("stream_reasoning", {
            "content": content, "agent_id": agent_id, "session_id": session_id,
        })

    async def on_tool(name: str, status: str, data: dict = None):
        payload = {
            "name": name, "status": status,
            "agent_id": agent_id, "session_id": session_id,
        }
        if data:
            payload.update(data)
        await ws.broadcast("stream_tool", payload)

    return on_text, on_reasoning, on_tool


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
        on_event = _make_event_handler(ctx.ws_manager)

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


@router.get("/chat/history")
async def chat_history(ctx: AppContext = Depends(get_ctx), scene_id: str = "default", limit: int = 50):
    return {"messages": ctx.db.messages.get_chat_history(scene_id, limit)}
