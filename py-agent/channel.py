"""Channel base class and ChatMessage format."""


import uuid


class ChatMessage:
    """Unified chat message format across all channels."""
    def __init__(self, content: str, user_id: str = "", user_name: str = "",
                 msg_type: str = "text", channel_type: str = "", scene_id: str = "",
                 msg_id: str = "", **kwargs):
        self.content = content
        self.user_id = user_id
        self.user_name = user_name
        self.msg_type = msg_type
        self.channel_type = channel_type
        self.scene_id = scene_id
        self.msg_id = msg_id or str(uuid.uuid4())[:8]
        self.extra = kwargs

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "msg_type": self.msg_type,
            "channel_type": self.channel_type,
            "scene_id": self.scene_id,
            "msg_id": self.msg_id,
            **self.extra,
        }


class Channel:
    """Base class for external communication channels."""
    def __init__(self):
        self._connected = False
        self.on_message = None

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self, scene_id: str, config: dict):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def is_running(self) -> bool:
        return self._connected

    def send(self, reply: str, user_id: str):
        raise NotImplementedError
