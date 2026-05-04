"""Channel base class and ChatMessage format."""


class ChatMessage:
    """Unified chat message format across all channels."""
    def __init__(self, content: str, user_id: str = "", user_name: str = "", msg_type: str = "text", **kwargs):
        self.content = content
        self.user_id = user_id
        self.user_name = user_name
        self.msg_type = msg_type
        self.extra = kwargs

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "msg_type": self.msg_type,
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
