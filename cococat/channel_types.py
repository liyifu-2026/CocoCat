"""Channel types — rich media message types for platform adapters.

Based on Hanako's content block system but adapted for CocoCat's
multi-channel (WeChat, ilink, Feishu) architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    FILE = "file"
    VIDEO = "video"
    STICKER = "sticker"
    LOCATION = "location"
    LINK = "link"
    POST = "post"  # Feishu rich text
    INTERACTIVE = "interactive"  # Feishu card
    EVENT = "event"  # Platform events (subscribe, etc.)


class ReplyType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    FILE = "file"
    VIDEO = "video"
    CARD = "card"  # Interactive / news card
    POST = "post"  # Rich text (Feishu)
    ERROR = "error"


@dataclass
class MediaAttachment:
    """Media file attached to a message."""
    type: str  # image, voice, file, video
    media_id: str = ""  # Platform-specific ID for download
    url: str = ""  # Direct URL if available
    filename: str = ""
    mime_type: str = ""
    size: int = 0
    duration: int = 0  # For voice/video
    data: Optional[bytes] = None  # Downloaded content


@dataclass
class ChatMessage:
    """Rich media chat message from any channel."""
    channel_type: str = ""
    scene_id: str = ""
    user_id: str = ""
    content: str = ""
    msg_type: MessageType = MessageType.TEXT
    msg_id: str = ""
    media: list[MediaAttachment] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    # Feishu-specific
    mention_list: list[str] = field(default_factory=list)
    thread_id: str = ""
    # Location
    location: Optional[dict] = None  # {lat, lng, address}


@dataclass
class Reply:
    """Reply to a channel message."""
    type: ReplyType
    content: str = ""
    media_path: str = ""  # Local file path for image/file/video
    media_url: str = ""  # Remote URL fallback
    card_data: Optional[dict] = None  # For CARD type
    # Streaming (Feishu typewriter)
    streaming: bool = False
    replace_message_id: str = ""  # For updating a card in-place


@dataclass
class CardData:
    """Feishu interactive card / WeChat news card."""
    title: str = ""
    content: str = ""
    image_url: str = ""
    url: str = ""
    buttons: list[dict] = field(default_factory=list)
    # Feishu CardKit
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


# Platform capabilities (from spec)
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
