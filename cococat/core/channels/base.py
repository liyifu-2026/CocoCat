"""Channel base class with 4-state connection, startup event, and media helpers."""
from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable, Optional, Protocol

from .context import Context, Reply, ReplyType, MediaCapabilities

logger = logging.getLogger("cococat.channel")


class Channel(Protocol):
    """Lightweight interface for channel routing (used by SceneKeeper).

    Just parse_identity() and send() — the minimum a router needs to know.
    """

    async def parse_identity(self, raw_msg: dict) -> str:
        """Extract user identity from raw channel message."""
        ...

    async def send(self, user_id: str, text: str) -> None:
        """Send a text reply to a user through the channel."""
        ...


class ChatMessage:
    """Unified message format across all channels."""

    def __init__(self, channel_type="", scene_id="", user_id="",
                 content="", msg_type="text", msg_id="", **kwargs):
        self.channel_type = channel_type
        self.scene_id = scene_id
        self.user_id = user_id
        self.content = content
        self.msg_type = msg_type
        self.msg_id = msg_id or str(uuid.uuid4())[:8]
        self.extra = kwargs


class ChannelBase:
    """Base class for external communication channels.

    Subclasses must set channel_type and implement startup() and send().
    """

    channel_type = ""
    caps: MediaCapabilities | None = None

    CONN_DISCONNECTED = "disconnected"
    CONN_CONNECTING = "connecting"
    CONN_CONNECTED = "connected"
    CONN_RECONNECTING = "reconnecting"

    def __init__(self):
        self.scene_id = ""
        self.on_message: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.connected_state = ChannelBase.CONN_DISCONNECTED
        self._startup_event = threading.Event()
        self._startup_error = None
        self._config = {}

    def startup(self):
        """Initialize channel connection. Called by start() in a background thread."""
        raise NotImplementedError

    def start(self, scene_id: str, config: dict):
        """Start the channel in a background thread and report completion via startup_event."""
        self.scene_id = scene_id
        self._config = config
        self.connected_state = ChannelBase.CONN_CONNECTING
        self._startup_event.clear()
        self._startup_error = None
        t = threading.Thread(target=self._startup_wrapper, daemon=True)
        t.start()

    def _startup_wrapper(self):
        try:
            self.startup()
        except Exception as e:
            self.connected_state = ChannelBase.CONN_DISCONNECTED
            self.report_startup_error(str(e))

    def report_startup_success(self):
        self._startup_error = None
        self._startup_event.set()

    def report_startup_error(self, error: str):
        self._startup_error = error
        self._startup_event.set()

    def wait_startup(self, timeout: float = 3) -> tuple[bool, str]:
        """Wait for channel startup result. Returns (success, error_msg)."""
        ready = self._startup_event.wait(timeout=timeout)
        if not ready:
            return False, "timeout"
        if self._startup_error:
            return False, self._startup_error
        return True, ""

    def _compose_context(self, ctype, content, **kwargs):
        """Build a Context with channel metadata injected."""
        from .context import Context as Ctx
        return Ctx(ctype, content, channel_type=self.channel_type, origin_ctype=ctype, **kwargs)

    def _generate_reply(self, ctx):
        """Generate a Reply via on_message callback, or echo stub if no callback."""
        if self.on_message:
            msg = ctx.get("msg")
            result = self.on_message(msg) if msg else self.on_message(ctx)
            if result:
                return Reply(ReplyType.TEXT, result)
            return Reply(ReplyType.TEXT, "")
        return Reply(ReplyType.TEXT, ctx.content)

    def send(self, reply: Reply, context: Context):
        """Send a Reply object through this channel.

        Args:
            reply: Reply object with type and content.
            context: Context object with receiver/session metadata.
        """
        raise NotImplementedError

    def stop(self):
        self.connected_state = ChannelBase.CONN_DISCONNECTED

    def is_running(self) -> bool:
        return self.connected_state in (
            ChannelBase.CONN_CONNECTED,
            ChannelBase.CONN_CONNECTING,
            ChannelBase.CONN_RECONNECTING,
        )

    # ── Rich reply helpers ─────────────────────────────────

    def text_reply(self, content: str) -> Reply:
        return Reply(ReplyType.TEXT, content=content)

    def image_reply(self, file_path: str) -> Reply:
        return Reply(ReplyType.IMAGE, media_path=file_path)

    def file_reply(self, file_path: str, filename: str = "") -> Reply:
        return Reply(ReplyType.FILE, media_path=file_path, content=filename)

    def card_reply(self, card_data: dict) -> Reply:
        return Reply(ReplyType.CARD, card_data=card_data)

    def streaming_card(self, card_data: dict, replace_id: str = "") -> Reply:
        return Reply(ReplyType.CARD, card_data=card_data,
                     streaming=True, replace_message_id=replace_id)

    # ── Text chunking ──────────────────────────────────────

    def chunk_text(self, text: str) -> list[str]:
        """Split long text into chunks for platforms with length limits."""
        limit = self.caps.max_text_length if self.caps else 0
        if not limit or len(text) <= limit:
            return [text]

        chunks = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, limit)
            if split_at == -1 or split_at < limit // 2:
                split_at = text.rfind(" ", 0, limit)
            if split_at == -1 or split_at < limit // 2:
                split_at = limit
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip()
        return chunks

    def send_chunked(self, text: str, reply_fn, *args) -> int:
        """Send text in chunks if caps allow. Calls reply_fn(chunk, *args) for each. Returns chunk count."""
        if self.caps and self.caps.chunk_long_text:
            chunks = self.chunk_text(text)
        else:
            chunks = [text]
        sent = 0
        for chunk in chunks:
            reply_fn(chunk, *args)
            sent += 1
        return sent
