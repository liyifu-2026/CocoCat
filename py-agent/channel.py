"""Channel base class with 4-state connection and startup event (CowAgent pattern)."""
from __future__ import annotations

import threading
import uuid


class ChatMessage:
    """Unified message format across all channels.

    Created by channel implementations when receiving platform messages.
    Passed to _compose_context() via kwargs as msg=.
    """
    def __init__(self, channel_type="", scene_id="", user_id="",
                 content="", msg_type="text", msg_id="", **kwargs):
        self.channel_type = channel_type
        self.scene_id = scene_id
        self.user_id = user_id
        self.content = content
        self.msg_type = msg_type
        self.msg_id = msg_id or str(uuid.uuid4())[:8]
        self.extra = kwargs


class Channel:
    """Base class for external communication channels.

    Subclasses must set channel_type and implement startup() and send().
    """
    channel_type = ""

    CONN_DISCONNECTED = "disconnected"
    CONN_CONNECTING = "connecting"
    CONN_CONNECTED = "connected"
    CONN_RECONNECTING = "reconnecting"

    def __init__(self):
        self.scene_id = ""
        self.on_message = None
        self.on_disconnected = None
        self.connected_state = Channel.CONN_DISCONNECTED
        self._startup_event = threading.Event()
        self._startup_error = None
        self._config = {}

    def startup(self):
        """Initialize channel connection. Called by start() in a background thread."""
        raise NotImplementedError

    def start(self, scene_id: str, config: dict):
        """Start the channel in a background thread and report completion via startup_event."""
        self.scene_id = scene_id
        self._config = config
        self.connected_state = Channel.CONN_CONNECTING
        self._startup_event.clear()
        self._startup_error = None
        t = threading.Thread(target=self._startup_wrapper, daemon=True)
        t.start()

    def _startup_wrapper(self):
        try:
            self.startup()
        except Exception as e:
            self.connected_state = Channel.CONN_DISCONNECTED
            self.report_startup_error(str(e))

    def report_startup_success(self):
        self._startup_error = None
        self._startup_event.set()

    def report_startup_error(self, error: str):
        self._startup_error = error
        self._startup_event.set()

    def wait_startup(self, timeout: float = 3) -> tuple[bool, str]:
        """Wait for channel startup result. Returns (success, error_msg)."""
        ready = self._startup_event.wait(timeout=timeout)
        if not ready:
            return False, "timeout"
        if self._startup_error:
            return False, self._startup_error
        return True, ""

    def send(self, reply, context):
        """Send a Reply object through this channel.

        Args:
            reply: Reply object with type and content.
            context: Context object with receiver/session metadata.
        """
        raise NotImplementedError

    def stop(self):
        self.connected_state = Channel.CONN_DISCONNECTED

    def is_running(self) -> bool:
        return self.connected_state in (
            Channel.CONN_CONNECTED,
            Channel.CONN_CONNECTING,
            Channel.CONN_RECONNECTING,
        )
