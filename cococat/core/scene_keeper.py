"""SceneKeeper — lightweight channel-message router for business scenes.

Each Scene has one SceneKeeper (not AI). It:
  - Receives messages from the scene's channel
  - Parses user identity via channel.parse_identity()
  - Triggers ExecutorProvider.run_once() with scene permissions
  - Sends the agent's reply back through the channel
"""
from __future__ import annotations

import logging
from typing import Any

from cococat.core.channels.base import Channel

logger = logging.getLogger("cococat.scene_keeper")


class SceneKeeper:
    """Lightweight router between a channel and the ExecutorProvider.

    Not an AI. Does not reason. Just:
      receive → parse identity → create sandbox → execute agent → send reply
    """

    def __init__(
        self,
        scene_id: str,
        channel: Channel,
        sandbox_provider: Any,
        scene_permissions: dict | None = None,
        max_retries: int = 1,
        timeout_seconds: int = 120,
        fallback_reply: str = "抱歉，系统繁忙，请稍后再试。",
    ):
        self.scene_id = scene_id
        self._channel = channel
        self._sandbox = sandbox_provider
        self._permissions = scene_permissions or {}
        self._max_retries = max_retries
        self._timeout = timeout_seconds
        self._fallback_reply = fallback_reply

    async def handle_message(self, raw_msg: dict) -> None:
        """Handle an incoming channel message.

        1. Parse user identity
        2. Trigger sandbox agent with scene permissions
        3. Send reply
        4. On failure: retry once, then fallback reply
        """
        user_id = await self._channel.parse_identity(raw_msg)
        prompt = raw_msg.get("text", "")

        for attempt in range(self._max_retries + 1):
            try:
                result = await self._sandbox.run_once(
                    prompt=prompt,
                    agent_id=f"scene-{self.scene_id}",
                    permissions=self._permissions,
                )
                await self._channel.send(user_id, result)
                return
            except Exception as e:
                logger.warning(
                    "SceneKeeper[%s]: attempt %d/%d failed: %s",
                    self.scene_id, attempt + 1, self._max_retries + 1, e
                )
                if attempt >= self._max_retries:
                    await self._channel.send(user_id, self._fallback_reply)
