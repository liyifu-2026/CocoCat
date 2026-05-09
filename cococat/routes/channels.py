"""Channel management routes."""
import json
import os
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/channels", tags=["channels"])


class ChannelConnect(BaseModel):
    target_type: str  # "scene" or "main"
    target_id: str
    channel_type: str
    config: dict = {}


CHANNEL_STATUS: dict[str, dict] = {}


@router.get("")
async def list_channels(request: Request):
    """List all configured channels."""
    result = []
    scenes_dir = "scenes"
    if os.path.isdir(scenes_dir):
        for scene_id in os.listdir(scenes_dir):
            path = os.path.join(scenes_dir, scene_id, "scene.yaml")
            if not os.path.exists(path):
                continue
            import yaml
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for ch in data.get("channels", []):
                key = f"scene:{scene_id}:{ch['type']}"
                result.append({
                    "target_type": "scene",
                    "target_id": scene_id,
                    "channel_type": ch["type"],
                    "status": CHANNEL_STATUS.get(key, {}).get("status", "stopped"),
                })

    return {"channels": result}


@router.post("/connect")
async def connect_channel(body: ChannelConnect, request: Request):
    """Connect/start a channel."""
    key = f"{body.target_type}:{body.target_id}:{body.channel_type}"

    try:
        # Try to create and start the channel via old channel factory
        import sys
        sys.path.insert(0, "py-agent")
        from channels.channel_factory import create_channel

        ch = create_channel(body.channel_type)

        # Set up message routing
        if body.target_type == "scene":
            pool = request.app.state.pool
            bus = request.app.state.bus

            async def route(msg, scene_id=body.target_id, ct=body.channel_type):
                agent = pool.get_scene_agent(scene_id)
                if agent:
                    reply = await agent.run(msg.content)
                    await ch.send(reply, msg.user_id)
                await bus.publish("scene_message", {
                    "scene_id": scene_id,
                    "channel": ct,
                    "user_id": msg.user_id,
                    "content": msg.content,
                })

            ch.on_message = route
            ch.start(body.target_id, body.config)

        CHANNEL_STATUS[key] = {"status": "connected", "channel_type": body.channel_type}
        return {"status": "connected"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/disconnect")
async def disconnect_channel(body: ChannelConnect, request: Request):
    """Disconnect/stop a channel."""
    key = f"{body.target_type}:{body.target_id}:{body.channel_type}"
    CHANNEL_STATUS.pop(key, None)
    return {"status": "disconnected"}
