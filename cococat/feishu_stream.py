"""Feishu streaming card — typewriter effect via progressive card updates."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable, Optional

logger = logging.getLogger("cococat.channel.feishu_stream")


class StreamingCard:
    """Feishu typewriter card — progressively updates a card message.

    Usage:
        card = StreamingCard(msg_id, send_fn)
        await card.start()
        await card.update("Loading...")
        await card.update("Processing step 1...")
        await card.finish("Done! Here are the results.")
    """

    def __init__(
        self,
        message_id: str,
        send_card: Callable[[dict, str], Awaitable[bool]],  # (card_data, replace_id) → bool
        interval: float = 0.5,
    ):
        self._msg_id = message_id
        self._send = send_card
        self._interval = interval
        self._content: list[str] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self, title: str = "Processing...") -> None:
        """Begin streaming with initial card."""
        self._running = True
        card = self._build_card(title, "")
        await self._send(card, self._msg_id)

    async def update(self, text: str) -> None:
        """Append text to the streaming card."""
        self._content.append(text)
        card = self._build_card("Processing...", "\n\n".join(self._content))
        await self._send(card, self._msg_id)
        await asyncio.sleep(self._interval)

    async def finish(self, final_text: str, title: str = "Done") -> None:
        """Send final card content."""
        self._running = False
        card = self._build_card(title, final_text)
        await self._send(card, self._msg_id)

    @staticmethod
    def _build_card(title: str, content: str) -> dict:
        """Build a Feishu CardKit card."""
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue" if title == "Processing..." else "green",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": content or "_No content yet..._",
                }
            ],
        }


class FeishuStreamManager:
    """Manages multiple streaming cards per Feishu channel."""

    def __init__(self):
        self._cards: dict[str, StreamingCard] = {}

    def create(
        self,
        message_id: str,
        send_card: Callable[[dict, str], Awaitable[bool]],
    ) -> StreamingCard:
        card = StreamingCard(message_id, send_card)
        self._cards[message_id] = card
        return card

    def get(self, message_id: str) -> Optional[StreamingCard]:
        return self._cards.get(message_id)

    def remove(self, message_id: str) -> None:
        self._cards.pop(message_id, None)
