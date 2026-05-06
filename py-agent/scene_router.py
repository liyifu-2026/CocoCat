"""Routes entry messages to scene-level user storage."""
import os
import json
from datetime import datetime

_BASE = None  # test seam: set to override base directory


def _scenes_dir() -> str:
    if _BASE:
        return _BASE
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scenes"))


def store_message(scene_id: str, user_id: str, msg_dict: dict):
    """Store a message in scenes/{scene_id}/users/{user_id}/history.jsonl."""
    history_dir = os.path.join(_scenes_dir(), scene_id, "users", user_id)
    history_path = os.path.join(history_dir, "history.jsonl")
    os.makedirs(history_dir, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "direction": msg_dict.get("direction", "incoming"),
        "content": msg_dict.get("content", ""),
        "channel": msg_dict.get("channel_type", ""),
    }
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_history(scene_id: str, user_id: str, limit: int = 20) -> list[dict]:
    """Read recent conversation history for a user in a scene."""
    history_path = os.path.join(_scenes_dir(), scene_id, "users", user_id, "history.jsonl")
    if not os.path.exists(history_path):
        return []

    entries = []
    with open(history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-limit:]


def create_bus_subscriber(bus):
    """Record all inbound/outbound messages as scene history."""
    def on_inbound(msg):
        if msg.scene_id:
            store_message(msg.scene_id, msg.source, {
                "timestamp": __import__("time").time(),
                "direction": "incoming",
                "content": msg.content,
                "channel": msg.channel,
            })

    def on_outbound(msg):
        scene_id = msg.metadata.get("scene_id")
        if scene_id:
            store_message(scene_id, msg.target, {
                "timestamp": __import__("time").time(),
                "direction": "outgoing",
                "content": msg.content,
                "channel": msg.channel,
            })

    bus.subscribe_inbound(on_inbound)
    bus.subscribe_outbound(on_outbound)
