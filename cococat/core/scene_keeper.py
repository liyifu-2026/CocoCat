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

    async def handle_message(self, content: str, mode: str = "default") -> str:
        """Process a message through the sandbox agent. Returns reply text.

        Retries up to max_retries times on failure, then returns fallback_reply.
        """
        for attempt in range(self._max_retries + 1):
            try:
                return await self._sandbox.run_once(
                    prompt=content,
                    agent_id="coco",
                    scene_id=self.scene_id,
                    permissions=self._permissions,
                    mode=mode,
                )
            except Exception as e:
                logger.warning(
                    "SceneKeeper[%s]: attempt %d/%d failed: %s",
                    self.scene_id, attempt + 1, self._max_retries + 1, e,
                )
                if attempt >= self._max_retries:
                    return self._fallback_reply
        return self._fallback_reply
