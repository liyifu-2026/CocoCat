"""Context and Reply types for channel message processing."""
from __future__ import annotations

from enum import Enum


class ContextType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    IMAGE_CREATE = "image_create"
    FILE = "file"
    VIDEO = "video"
    SHARING = "sharing"
    FUNCTION = "function"


class ReplyType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    IMAGE_URL = "image_url"
    FILE = "file"
    VIDEO = "video"
    VIDEO_URL = "video_url"
    ERROR = "error"
    INFO = "info"


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
    def __init__(self, rtype: ReplyType, content: str):
        self.type = rtype
        self.content = content
