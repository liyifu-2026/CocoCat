from __future__ import annotations

import threading
from queue import Queue, Empty
from typing import Callable

from message import InboundMessage, OutboundMessage


class MessageBus:
    def __init__(self):
        self._inbound: Queue[InboundMessage] = Queue()
        self._outbound: Queue[OutboundMessage] = Queue()
        self._inbound_handlers: list[Callable[[InboundMessage], None]] = []
        self._outbound_handlers: list[Callable[[OutboundMessage], None]] = []
        self._lock = threading.Lock()
        self._inbound_event = threading.Event()

    def publish_inbound(self, msg: InboundMessage):
        self._inbound.put(msg)
        self._inbound_event.set()
        for handler in self._inbound_handlers:
            try:
                handler(msg)
            except Exception:
                pass

    def publish_outbound(self, msg: OutboundMessage):
        self._outbound.put(msg)
        for handler in self._outbound_handlers:
            try:
                handler(msg)
            except Exception:
                pass

    def subscribe_inbound(self, handler: Callable[[InboundMessage], None]):
        with self._lock:
            self._inbound_handlers.append(handler)

    def subscribe_outbound(self, handler: Callable[[OutboundMessage], None]):
        with self._lock:
            self._outbound_handlers.append(handler)

    def wait_for_inbound(self, timeout: float | None = None) -> InboundMessage | None:
        self._inbound_event.wait(timeout=timeout)
        self._inbound_event.clear()
        try:
            return self._inbound.get_nowait()
        except Empty:
            return None

    def drain_inbound(self) -> list[InboundMessage]:
        msgs = []
        while not self._inbound.empty():
            try:
                msgs.append(self._inbound.get_nowait())
            except Empty:
                break
        return msgs
