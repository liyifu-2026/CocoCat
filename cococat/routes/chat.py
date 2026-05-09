"""Chat routes."""
from fastapi import APIRouter, Request
from pydantic import BaseModel

from cococat.db import new_uuid

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    content: str
    user_id: str = "local"
    scene_id: str = "default"


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """Send a message to Main AI."""
    db = request.app.state.db
    pool = request.app.state.pool

    msg_uuid = new_uuid()
    db.execute_insert(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, channel_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (msg_uuid, "main", body.user_id, "user", body.content, body.scene_id, "web"),
    )

    main_ai = pool.get_agent("main")
    if not main_ai:
        # Fallback: return static response if agent pool not populated
        reply_uuid = new_uuid()
        db.execute_insert(
            "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (reply_uuid, "main", body.user_id, "assistant",
             f"[System] Main AI not connected. Received: {body.content[:200]}",
             body.scene_id),
        )
        return {"reply": "Main AI not connected", "msg_uuid": reply_uuid}

    try:
        reply = await main_ai.run(body.content)
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
async def chat_history(request: Request, scene_id: str = "default", limit: int = 50):
    db = request.app.state.db
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
