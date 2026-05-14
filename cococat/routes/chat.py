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


@router.post("/chat")
async def chat(body: ChatRequest, ctx: AppContext = Depends(get_ctx)):
    """Send a message to Main AI via SandboxProvider."""
    db = ctx.db

    msg_uuid = new_uuid()
    db.execute_insert(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, channel_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (msg_uuid, "main", body.user_id, "user", body.content, body.scene_id, "web"),
    )

    sandbox_provider = ctx.sandbox_provider
    if not sandbox_provider:
        reply_uuid = new_uuid()
        db.execute_insert(
            "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (reply_uuid, "main", body.user_id, "assistant",
             f"[System] SandboxProvider not available. Received: {body.content[:200]}",
             body.scene_id),
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
            })

        async def on_reasoning(content: str):
            await ws.broadcast("stream_reasoning", {
                "content": content,
                "agent_id": "main",
            })

        async def on_tool(name: str, status: str):
            await ws.broadcast("stream_tool", {
                "name": name,
                "status": status,
                "agent_id": "main",
            })

        from cococat.core.tools import create_main_ai_tools

        sub_executor = ctx.sub_executor
        main_ai_tools = create_main_ai_tools(
            sub_agent_executor=sub_executor.dispatch if sub_executor else None,
        )

        reply = await sandbox_provider.run_once(
            prompt=body.content,
            agent_id="main",
            tools=main_ai_tools,
            on_event=on_event,
        )

        from cococat.core.agent import _save_session_pair
        import os
        _save_session_pair(os.path.join("agents/main", "session.jsonl"), body.content, reply)
    except Exception as e:
        reply = f"Error: {e}"

    reply_uuid = new_uuid()
    db.execute_insert(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (reply_uuid, "main", body.user_id, "assistant", reply, body.scene_id),
    )
    return {"reply": reply, "msg_uuid": reply_uuid}


@router.get("/chat/history")
async def chat_history(ctx: AppContext = Depends(get_ctx), scene_id: str = "default", limit: int = 50):
    db = ctx.db
    rows = db.execute(
        "SELECT role, content, created_at FROM messages "
        "WHERE scene_id = ? AND chat_group = 'general' "
        "ORDER BY id DESC LIMIT ?",
        (scene_id, limit),
    )
    return {
        "messages": [
            {"role": r[0], "content": r[1], "created_at": r[2]}
            for r in reversed(rows)
        ]
    }
