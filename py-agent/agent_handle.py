"""AgentHandle — runtime reference to an agent process via mailbox communication."""
from __future__ import annotations

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger("cococat.agent_handle")


def _mailbox_dir() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "mailbox")
    )


class AgentHandle:
    """Runtime handle to an agent, communicating via mailbox files.

    The agent process polls agents/mailbox/{agent_id}/inbox.jsonl for new messages.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.scene_id: str | None = None

    @property
    def is_assigned(self) -> bool:
        return self.scene_id is not None

    def assign_to_scene(self, scene_id: str, scene_context: str):
        """Send a scene_assign command to the agent's mailbox."""
        self.scene_id = scene_id
        self._send_command("scene_assign", {
            "scene_id": scene_id,
            "context": scene_context,
        })
        logger.info(f"Agent {self.agent_id} assigned to scene {scene_id}")

    def release(self):
        """Send a scene_release command and clear assignment."""
        if self.scene_id:
            self._send_command("scene_release", {"scene_id": self.scene_id})
            logger.info(f"Agent {self.agent_id} released from scene {self.scene_id}")
            self.scene_id = None

    def send_message(self, channel: str, user_id: str, content: str) -> str | None:
        """Write a user message to the agent's inbox. Returns message_id."""
        mailbox_dir = os.path.join(_mailbox_dir(), self.agent_id)
        os.makedirs(mailbox_dir, exist_ok=True)
        inbox_path = os.path.join(mailbox_dir, "inbox.jsonl")

        from sandbox import FileLock
        entry = {
            "from": f"scene:{self.scene_id}:{channel}:{user_id}",
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "status": "unread",
            "scene_id": self.scene_id,
            "channel": channel,
            "external_user": user_id,
        }
        with FileLock(inbox_path):
            with open(inbox_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry.get("from")

    def _send_command(self, command: str, data: dict):
        """Write a system command to the agent's control mailbox."""
        mailbox_dir = os.path.join(_mailbox_dir(), self.agent_id)
        os.makedirs(mailbox_dir, exist_ok=True)
        control_path = os.path.join(mailbox_dir, "control.jsonl")

        from sandbox import FileLock
        entry = {
            "command": command,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        with FileLock(control_path):
            with open(control_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
