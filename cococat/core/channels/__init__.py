"""Channel package — platform channel adapters."""
from .base import ChannelBase, ChatMessage  # noqa: F401 — re-exports
from .context import Context, Reply, ReplyType, ContextType  # noqa: F401
from .factory import create_channel, register_channel  # noqa: F401
from .reconnecting import ReconnectingChannel  # noqa: F401

# Auto-register all channel implementations
from . import wechat   # noqa: F401
from . import feishu   # noqa: F401
from . import weixin   # noqa: F401
from . import discord  # noqa: F401
from . import telegram # noqa: F401
