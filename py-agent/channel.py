"""Channel base class and unified message format (CowAgent pattern)."""
from datetime import datetime
import json


class ChatMessage:
    """Unified message format across all channels."""
    def __init__(self, channel_type="", scene_id="", user_id="",
                 content="", msg_type="text", msg_id="", timestamp=None):
        self.channel_type = channel_type
        self.scene_id = scene_id
        self.user_id = user_id
        self.content = content
        self.msg_type = msg_type
        self.msg_id = msg_id or str(datetime.now().timestamp())
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self):
        return {
            "channel_type": self.channel_type,
            "scene_id": self.scene_id,
            "user_id": self.user_id,
            "content": self.content,
            "msg_type": self.msg_type,
            "msg_id": self.msg_id,
            "timestamp": self.timestamp,
        }


class Channel:
    """Base class for scene entry channels.

    Subclasses must set channel_type and implement start() and send().
    """
    channel_type = ""

    def __init__(self):
        self.scene_id = ""
        self.on_message = None

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        raise NotImplementedError

    def send(self, reply: str, user_id: str):
        raise NotImplementedError
