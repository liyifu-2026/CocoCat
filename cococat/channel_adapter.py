"""Channel adapter — base class for platform channel implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable, Awaitable, Optional

from cococat.channel_types import (
    ChatMessage, Reply, ReplyType, MediaCapabilities,
)

logger = logging.getLogger("cococat.channel")


class ChannelAdapter(ABC):
    """Base class for all channel platform adapters.

    Each platform (WeChat, ilink, Feishu) implements this interface.
    The adapter handles: connection, message receive, reply send,
    media download/upload, and capability declaration.
    """

    def __init__(self, caps: MediaCapabilities):
        self.caps = caps
        self._on_message: Optional[Callable[[ChatMessage], Awaitable[None]]] = None

    @property
    def on_message(self):
        return self._on_message

    @on_message.setter
    def on_message(self, handler: Callable[[ChatMessage], Awaitable[None]]):
        self._on_message = handler

    @abstractmethod
    async def start(self, scene_id: str, config: dict) -> None:
        """Start the channel connection."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel connection."""
        ...

    @abstractmethod
    async def send(self, reply: Reply, user_id: str) -> bool:
        """Send a reply to a user. Returns True on success."""
        ...

    # ── Media Operations ──

    async def download_media(self, media_id: str, media_type: str) -> Optional[bytes]:
        """Download media file from platform. Override in platform subclass."""
        logger.warning("download_media not implemented for %s", type(self).__name__)
        return None

    async def upload_media(self, file_path: str, media_type: str) -> Optional[str]:
        """Upload media file to platform. Returns media_id. Override in subclass."""
        logger.warning("upload_media not implemented for %s", type(self).__name__)
        return None

    # ── Rich Reply Helpers ──

    def text_reply(self, content: str) -> Reply:
        return Reply(type=ReplyType.TEXT, content=content)

    def image_reply(self, file_path: str) -> Reply:
        return Reply(type=ReplyType.IMAGE, media_path=file_path)

    def file_reply(self, file_path: str, filename: str = "") -> Reply:
        return Reply(type=ReplyType.FILE, media_path=file_path, content=filename)

    def card_reply(self, card_data: dict) -> Reply:
        return Reply(type=ReplyType.CARD, card_data=card_data)

    def streaming_card(self, card_data: dict, replace_id: str = "") -> Reply:
        """Feishu typewriter card — progressively updates."""
        return Reply(type=ReplyType.CARD, card_data=card_data,
                     streaming=True, replace_message_id=replace_id)

    # ── Text Handling ──

    def chunk_text(self, text: str) -> list[str]:
        """Split long text into chunks for platforms with length limits."""
        limit = self.caps.max_text_length
        if not limit or len(text) <= limit:
            return [text]

        chunks = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            # Find a break point
            split_at = text.rfind("\n", 0, limit)
            if split_at == -1 or split_at < limit // 2:
                split_at = text.rfind(" ", 0, limit)
            if split_at == -1 or split_at < limit // 2:
                split_at = limit
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip()
        return chunks

    async def send_chunked(self, text: str, user_id: str) -> int:
        """Send text in chunks if platform supports it. Returns chunk count."""
        if not self.caps.chunk_long_text:
            reply = self.text_reply(text)
            ok = await self.send(reply, user_id)
            return 1 if ok else 0

        chunks = self.chunk_text(text)
        sent = 0
        for chunk in chunks:
            reply = self.text_reply(chunk)
            if await self.send(reply, user_id):
                sent += 1
        return sent
