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


@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    """Send a message to Main AI via SandboxProvider."""
    msg_uuid = new_uuid()
    ctx.db.save_message(
        msg_uuid=msg_uuid, agent_id="main", user_id=body.user_id,
        role="user", content=body.content, scene_id=body.scene_id,
        channel_type="web",
    )

    sandbox_provider = ctx.sandbox_provider
    if not sandbox_provider:
        reply_uuid = new_uuid()
        ctx.db.save_message(
            msg_uuid=reply_uuid, agent_id="main", user_id=body.user_id,
            role="assistant",
            content=f"[System] SandboxProvider not available. Received: {body.content[:200]}",
            scene_id=body.scene_id,
        )
        return {"reply": "SandboxProvider not available", "msg_uuid": reply_uuid}

    try:
        ws = ctx.ws_manager

        async def on_event(event_type: str, data: dict):
            await ws.broadcast(event_type, data)

        async def on_text(delta: str):
            await ws.broadcast("text_delta", {
                "content": delta,
                "agent_id": "main",
                "session_id": body.session_id,
            })

        async def on_reasoning(content: str):
            await ws.broadcast("stream_reasoning", {
                "content": content,
                "agent_id": "main",
                "session_id": body.session_id,
            })

        async def on_tool(name: str, status: str, data: dict = None):
            payload = {
                "name": name,
                "status": status,
                "agent_id": "main",
                "session_id": body.session_id,
            }
            if data:
                payload.update(data)
            await ws.broadcast("stream_tool", payload)

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
    ctx.db.save_message(
        msg_uuid=reply_uuid, agent_id="main", user_id=body.user_id,
        role="assistant", content=reply, scene_id=body.scene_id,
    )
    return {"reply": reply, "msg_uuid": reply_uuid}


@router.get("/chat/history")
async def chat_history(ctx: AppContext = Depends(get_ctx), scene_id: str = "default", limit: int = 50):
    return {"messages": ctx.db.get_chat_history(scene_id, limit)}
