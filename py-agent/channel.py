"""Channel base class and ChatMessage format."""
from __future__ import annotations

import uuid

from message import InboundMessage, OutboundMessage


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

    def to_inbound(self, agent_id: str) -> InboundMessage:
        return InboundMessage(
            channel=self.channel_type or "unknown",
            source=self.user_id,
            content=self.content,
            agent_id=agent_id,
            scene_id=self.scene_id or "default",
            metadata={"msg_id": self.msg_id, "user_name": self.user_name},
        )


class Channel:
    """Base class for external communication channels."""
    def __init__(self, bus=None):
        self._connected = False
        self.bus = bus

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

    def reply(self, msg: OutboundMessage):
        """Send an outbound message back through this channel."""
        self.send(msg.content, msg.target)
