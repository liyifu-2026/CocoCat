"""Reply handler — receives agent replies via HTTP callback and routes to channels."""
import os
import sys
import logging
from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "py-agent"))

logger = logging.getLogger("cococat.reply_handler")

router = APIRouter()


class AgentReply(BaseModel):
    reply: str
    scene_id: str = ""
    channel: str = ""
    user_id: str = ""


@router.post("/api/channels/reply")
def handle_agent_reply(body: AgentReply):
    """Receive a reply from an agent and route to the appropriate channel."""
    if not body.scene_id or not body.channel or not body.user_id:
        logger.warning(f"Invalid reply: missing fields — {body}")
        return {"status": "error", "message": "missing scene_id, channel, or user_id"}

    try:
        from scene_manager import SceneManager
        mgr = SceneManager()
        runtime = mgr.get_runtime(body.scene_id)
        if runtime is None:
            logger.warning(f"Scene '{body.scene_id}' not found for reply")
            return {"status": "error", "message": "scene not found"}

        if runtime.state.name != "ACTIVE":
            logger.warning(f"Scene '{body.scene_id}' not active, dropping reply")
            # Write to outbox for later retry
            _write_outbox(body.scene_id, body.channel, body.user_id, body.reply)
            return {"status": "queued", "message": "scene not active, saved to outbox"}

        _send_reply(runtime, body.channel, body.user_id, body.reply)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Reply handler error: {e}")
        _write_outbox(body.scene_id, body.channel, body.user_id, body.reply)
        return {"status": "error", "message": str(e)}


def _send_reply(runtime, channel_type: str, user_id: str, content: str):
    """Send a reply through the correct channel."""
    from channel_context import Reply, ReplyType, Context, ContextType

    for ch in runtime.channels:
        if getattr(ch, "channel_type", "") == channel_type:
            reply = Reply(ReplyType.TEXT, content)
            ctx = Context(ContextType.TEXT, content, receiver=user_id)
            ch.send(reply, ctx)
            logger.info(f"Reply sent via {channel_type} to {user_id}")
            return

    logger.warning(f"No channel found for type '{channel_type}' in scene '{runtime.scene_id}'")


def _write_outbox(scene_id: str, channel_type: str, user_id: str, content: str):
    """Fallback: write undelivered reply to outbox file."""
    import json
    from datetime import datetime

    base = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "agents", "mailbox"
    ))
    outbox_path = os.path.join(base, "reply_outbox.jsonl")
    os.makedirs(base, exist_ok=True)

    entry = {
        "scene_id": scene_id,
        "channel": channel_type,
        "user_id": user_id,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    try:
        with open(outbox_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"Reply saved to outbox for {scene_id}/{channel_type}/{user_id}")
    except Exception as e:
        logger.error(f"Failed to write outbox: {e}")
