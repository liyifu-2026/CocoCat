"""Channel package — platform channel adapters."""
from .base import ChannelBase, Channel, ChatMessage  # noqa: F401
from .context import (  # noqa: F401
    Context, Reply, ReplyType, ContextType,
    MessageType, MediaAttachment, MediaCapabilities, CardData,
    WECHAT_MP_CAPS, ILINK_CAPS, FEISHU_CAPS, WEB_API_CAPS,
)
from .factory import create_channel, register_channel  # noqa: F401
from .reconnecting import ReconnectingChannel  # noqa: F401

# Auto-register all channel implementations
from . import wechat   # noqa: F401
from . import feishu   # noqa: F401
from . import weixin   # noqa: F401
from . import discord  # noqa: F401
from . import telegram # noqa: F401
