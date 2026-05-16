"""Context, Reply, and media types for channel message processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Message types ──────────────────────────────────────────

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    FILE = "file"
    VIDEO = "video"
    STICKER = "sticker"
    LOCATION = "location"
    LINK = "link"
    POST = "post"
    INTERACTIVE = "interactive"
    EVENT = "event"


class ContextType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    IMAGE_CREATE = "image_create"
    FILE = "file"
    VIDEO = "video"
    SHARING = "sharing"
    FUNCTION = "function"


class ReplyType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    FILE = "file"
    VIDEO = "video"
    IMAGE_URL = "image_url"
    VIDEO_URL = "video_url"
    CARD = "card"
    POST = "post"
    ERROR = "error"
    INFO = "info"


# ── Media types ────────────────────────────────────────────

@dataclass
class MediaAttachment:
    """Media file attached to a message."""
    type: str = ""
    media_id: str = ""
    url: str = ""
    filename: str = ""
    mime_type: str = ""
    size: int = 0
    duration: int = 0
    data: Optional[bytes] = None


@dataclass
class CardData:
    """Feishu interactive card / WeChat news card."""
    title: str = ""
    content: str = ""
    image_url: str = ""
    url: str = ""
    buttons: list[dict] = field(default_factory=list)
    elements: list[dict] = field(default_factory=list)
    header: Optional[dict] = None


class MediaCapabilities:
    """Declares what media types a channel supports for receive and send."""

    def __init__(
        self,
        receive: set[MessageType] | None = None,
        send: set[ReplyType] | None = None,
        streaming: bool = False,
        cards: bool = False,
        reactions: bool = False,
        threads: bool = False,
        chunk_long_text: bool = False,
        max_text_length: int = 0,
    ):
        self.receive = receive or {MessageType.TEXT}
        self.send = send or {ReplyType.TEXT}
        self.streaming = streaming
        self.cards = cards
        self.reactions = reactions
        self.threads = threads
        self.chunk_long_text = chunk_long_text
        self.max_text_length = max_text_length

    def can_receive(self, msg_type: MessageType) -> bool:
        return msg_type in self.receive

    def can_send(self, reply_type: ReplyType) -> bool:
        return reply_type in self.send


# ── Platform capability presets ────────────────────────────

WECHAT_MP_CAPS = MediaCapabilities(
    receive={MessageType.TEXT, MessageType.IMAGE, MessageType.VOICE,
             MessageType.LOCATION, MessageType.LINK, MessageType.EVENT},
    send={ReplyType.TEXT, ReplyType.IMAGE, ReplyType.VOICE, ReplyType.CARD},
    max_text_length=2048,
)

ILINK_CAPS = MediaCapabilities(
    receive={MessageType.TEXT, MessageType.IMAGE, MessageType.VOICE,
             MessageType.FILE, MessageType.VIDEO, MessageType.STICKER},
    send={ReplyType.TEXT, ReplyType.IMAGE, ReplyType.FILE, ReplyType.VIDEO, ReplyType.CARD},
    chunk_long_text=True,
    max_text_length=4000,
)

FEISHU_CAPS = MediaCapabilities(
    receive={MessageType.TEXT, MessageType.POST, MessageType.IMAGE,
             MessageType.VOICE, MessageType.FILE, MessageType.VIDEO,
             MessageType.STICKER, MessageType.LINK},
    send={ReplyType.TEXT, ReplyType.POST, ReplyType.CARD, ReplyType.IMAGE,
          ReplyType.VOICE, ReplyType.FILE, ReplyType.VIDEO},
    streaming=True,
    cards=True,
    reactions=True,
    threads=True,
)

WEB_API_CAPS = MediaCapabilities(
    receive={MessageType.TEXT},
    send={ReplyType.TEXT, ReplyType.ERROR, ReplyType.INFO},
    max_text_length=0,
)


# ── Context / Reply ────────────────────────────────────────

class Context:
    """Message context carrying content, type, and metadata through the pipeline."""
    def __init__(self, ctype: ContextType, content: str, **kwargs):
        self.type = ctype
        self.content = content
        self.kwargs = kwargs

    def __getitem__(self, key):
        return self.kwargs[key]

    def __setitem__(self, key, value):
        self.kwargs[key] = value

    def get(self, key, default=None):
        return self.kwargs.get(key, default)


class Reply:
    """Unified reply object with type and content."""
    def __init__(self, reply_type: ReplyType, content: str = "",
                 media_path: str = "", media_url: str = "",
                 card_data: Optional[dict] = None,
                 streaming: bool = False, replace_message_id: str = ""):
        self.type = reply_type
        self.content = content
        self.media_path = media_path
        self.media_url = media_url
        self.card_data = card_data
        self.streaming = streaming
        self.replace_message_id = replace_message_id
