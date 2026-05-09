"""Bridge — connects old channel system to new EventBus + AgentPool.

Strategy: don't rewrite channels. Wrap them so their on_message callback
publishes to EventBus instead of writing to mailbox JSONL.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.core.event_bus import EventBus
    from cococat.core.agent_pool import AgentPool

logger = logging.getLogger("cococat.bridge")


class ChannelBridge:
    """Bridge between old-style channels and new EventBus + AgentPool.

    Usage:
        # On startup, create bridge and wrap channels:
        bridge = ChannelBridge(bus, pool)

        # For scene channels:
        ch.on_message = bridge.make_scene_handler("customer-service", "wechat", ch)

        # For Main AI channels:
        ch.on_message = bridge.make_main_handler("wechat", ch)
    """

    def __init__(self, bus: EventBus, pool: AgentPool):
        self._bus = bus
        self._pool = pool

    def make_scene_handler(self, scene_id: str, channel_type: str, channel: Any):
        """Return an on_message callback for a scene-bound channel."""

        async def handler(user_id: str, content: str):
            logger.info("Scene message: %s → %s (%s)", user_id, scene_id, channel_type)

            # Find the agent bound to this scene
            agent = self._pool.get_scene_agent(scene_id)
            if not agent:
                logger.warning("No agent bound to scene %s", scene_id)
                return

            await self._bus.publish("scene_message", {
                "scene_id": scene_id,
                "channel": channel_type,
                "user_id": user_id,
                "content": content,
            })

            try:
                reply = await agent.run(content)
                await channel.send_text(user_id, reply)
            except Exception:
                logger.exception("Scene handler failed")

        return handler

    def make_main_handler(self, channel_type: str, channel: Any):
        """Return an on_message callback for Main AI channel."""

        async def handler(user_id: str, content: str):
            logger.info("Main AI message from %s via %s", user_id, channel_type)

            agent = self._pool.get_agent("main")
            if not agent:
                logger.warning("Main AI not available")
                return

            await self._bus.publish("main_message", {
                "channel": channel_type,
                "user_id": user_id,
                "content": content,
            })

            try:
                reply = await agent.run(content)
                await channel.send_text(user_id, reply)
            except Exception:
                logger.exception("Main AI handler failed")

        return handler
