from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InboundMessage:
    channel: str
    source: str
    content: str
    agent_id: str
    scene_id: str = "default"
    metadata: dict = field(default_factory=dict)


@dataclass
class OutboundMessage:
    channel: str
    target: str
    content: str
    metadata: dict = field(default_factory=dict)
