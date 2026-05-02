"""Web API channel — built-in, always available."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from channel import Channel, ChatMessage


class WebApiChannel(Channel):
    channel_type = "web_api"

    def start(self, scene_id: str, config: dict):
        self.scene_id = scene_id
        self.endpoint = config.get("endpoint", f"/api/scenes/{scene_id}/chat")

    def send(self, reply: str, user_id: str):
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "scenes", self.scene_id, "users", user_id, "replies.jsonl"
        )
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        entry = {"reply": reply, "timestamp": __import__("datetime").datetime.now().isoformat()}
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def receive_message(self, user_id: str, content: str) -> ChatMessage:
        msg = ChatMessage(
            channel_type="web_api",
            scene_id=self.scene_id,
            user_id=user_id,
            content=content,
        )
        return msg
