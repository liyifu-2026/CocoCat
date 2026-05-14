"""Channel management routes."""
import json
import os
import sys
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cococat.app import get_ctx
from cococat.context import AppContext

router = APIRouter(prefix="/api/channels", tags=["channels"])


CHANNEL_FACTORY_PATH = os.environ.get("CHANNEL_FACTORY_PATH", "py-agent")


def _get_channel_factory():
    """Lazily load channel_factory from the configured path."""
    factory_path = CHANNEL_FACTORY_PATH
    if factory_path not in sys.path:
        sys.path.insert(0, factory_path)
    try:
        from channels.channel_factory import create_channel
        return create_channel
    except ImportError as e:
        raise RuntimeError(
            f"Cannot import channel_factory from '{factory_path}'. "
            f"Set CHANNEL_FACTORY_PATH or ensure py-agent is installed."
        ) from e


class ChannelConnect(BaseModel):
    target_type: str  # "scene" or "main"
    target_id: str
    channel_type: str
    config: dict = {}


CHANNEL_STATUS: dict[str, dict] = {}


@router.get("")
async def list_channels():
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
async def connect_channel(body: ChannelConnect, ctx: AppContext = Depends(get_ctx)):
    """Connect/start a channel."""
    key = f"{body.target_type}:{body.target_id}:{body.channel_type}"

    try:
        create_channel = _get_channel_factory()
        ch = create_channel(body.channel_type)

        if body.target_type == "scene":
            pool = ctx.pool
            bus = ctx.bus

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
async def disconnect_channel(body: ChannelConnect):
    """Disconnect/stop a channel."""
    key = f"{body.target_type}:{body.target_id}:{body.channel_type}"
    CHANNEL_STATUS.pop(key, None)
    return {"status": "disconnected"}
