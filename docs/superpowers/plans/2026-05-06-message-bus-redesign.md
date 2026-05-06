# Message Bus Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace polling-based message delivery with event-driven message bus for real-time delivery.

**Architecture:** MessageBus with publish/subscribe pattern. Channels/chat_reader/mailbox publish `InboundMessage`, bus fans out to consumers (persistence, scene history, agent processing). Agent publishes `OutboundMessage` for responses.

**Tech Stack:** Python 3.10+, `queue.Queue`, `threading.Event`

---

## File Structure

```
Create: py-agent/message.py    — InboundMessage, OutboundMessage types
Create: py-agent/bus.py        — MessageBus (pub/sub, queues)
Modify: py-agent/channel.py    — bus-aware base channel
Modify: py-agent/mailbox.py    — add bus consumer
Modify: py-agent/scene_router.py — add bus consumer
Modify: py-agent/heartbeat.py  — remove polling, consume bus
Modify: py-agent/agent_loop.py — consume bus, publish outbound
Modify: py-agent/agent_runner.py — wire bus
```

---

### Task 1: Create `message.py` + `bus.py`

- [ ] **Step 1: Create `py-agent/message.py`**

```python
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
```

- [ ] **Step 2: Create `py-agent/bus.py`**

```python
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
```

- [ ] **Step 3: Verify imports**

```bash
PYTHONPATH=py-agent python3 -c "from message import InboundMessage, OutboundMessage; from bus import MessageBus; print('message bus OK')"
```

---

### Task 2: Wire consumers — mailbox, scene_router, agent_status

- [ ] **Step 1: Modify `py-agent/mailbox.py`**

Add a bus subscriber function that persists inbound messages to inbox.jsonl:

```python
def create_bus_subscriber(bus):
    """Create a bus consumer that persists inbound messages to mailbox files."""
    from message import InboundMessage

    def on_inbound(msg: InboundMessage):
        if msg.channel == "mailbox":
            import json, os
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "mailbox", msg.agent_id, "inbox.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            entry = {
                "from": msg.source,
                "content": msg.content,
                "timestamp": __import__("time").time(),
                "status": "unread",
                "channel": msg.channel,
                "metadata": msg.metadata,
            }
            with open(path, "a") as f:
                f.write(__import__("json").dumps(entry, ensure_ascii=False) + "\n")

    bus.subscribe_inbound(on_inbound)
```

- [ ] **Step 2: Modify `py-agent/scene_router.py`**

```python
def create_bus_subscriber(bus):
    """Record all inbound/outbound messages as scene history."""
    from message import InboundMessage, OutboundMessage

    def on_inbound(msg: InboundMessage):
        if msg.scene_id:
            store_message(msg.scene_id, msg.source, {
                "timestamp": __import__("time").time(),
                "direction": "incoming",
                "content": msg.content,
                "channel": msg.channel,
            })

    def on_outbound(msg: OutboundMessage):
        if msg.metadata.get("scene_id"):
            store_message(msg.metadata["scene_id"], msg.target, {
                "timestamp": __import__("time").time(),
                "direction": "outgoing",
                "content": msg.content,
                "channel": msg.channel,
            })

    bus.subscribe_inbound(on_inbound)
    bus.subscribe_outbound(on_outbound)
```

- [ ] **Step 3: Modify `py-agent/agent_status.py`**

Agent status is already file-based and works fine. No bus integration needed — status is not a message, it's a heartbeat signal.

---

### Task 3: Modify `channel.py` — bus-aware base channel

- [ ] **Step 1: Modify `py-agent/channel.py`**

```python
from __future__ import annotations

import uuid
from message import InboundMessage, OutboundMessage


class ChatMessage:
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
            "content": self.content, "user_id": self.user_id,
            "user_name": self.user_name, "msg_type": self.msg_type,
            "channel_type": self.channel_type, "scene_id": self.scene_id,
            "msg_id": self.msg_id, **self.extra,
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
```

---

### Task 4: Modify channel implementations — publish to bus

For each channel, replace the inline file-writing or direct routing with `self.bus.publish_inbound(msg.to_inbound(agent_id))`.

Pattern:
```python
# Before:
from entry_manager import _route_to_agent
_route_to_agent(agent_id, content, ...)

# After:
msg = ChatMessage(content=text, user_id=user_id, channel_type="telegram", scene_id=scene_id)
inbound = msg.to_inbound(agent_id)
self.bus.publish_inbound(inbound)
```

Files to modify:
- `py-agent/channels/telegram.py`
- `py-agent/channels/feishu.py`
- `py-agent/channels/discord.py`
- `py-agent/channels/weixin.py`

---

### Task 5: Modify `heartbeat.py` — consume bus, remove polling

- [ ] **Step 1: Replace mailbox/chat polling with bus consumption**

```python
def _heartbeat_loop(agent_id, agent_name, interval, scene, bus):
    """Heartbeat now only handles schedule + bus events."""
    global _heartbeat_running
    if _heartbeat_running:
        return
    _heartbeat_running = True
    try:
        from agent_runner import AgentRunner
        runner = AgentRunner(agent_id, agent_name, scene)

        while True:
            # Wait for bus events or interval
            msg = bus.wait_for_inbound(timeout=interval)
            if msg:
                prompt = msg.content
                _execute_task(agent_id, agent_name, {"id": f"{msg.channel}_{msg.source}", "task": prompt}, scene=scene, runner=runner)

            # Schedule check (unchanged)
            try:
                tasks = get_pending_tasks(agent_id)
                if tasks:
                    print(f"[Heartbeat] {agent_name} found {len(tasks)} pending task(s)", file=sys.stderr)
                    for task in tasks:
                        _execute_task(agent_id, agent_name, task, scene=scene, runner=runner)
            except Exception as e:
                print(f"[Heartbeat] Error: {e}", file=sys.stderr)
    finally:
        _heartbeat_running = False
```

---

### Task 6: Wire bus in `agent_runner.py` and startup

- [ ] **Step 1: `agent_runner.py`**

```python
from bus import MessageBus
from message import InboundMessage, OutboundMessage
# ...

class AgentRunner:
    def __init__(self, agent_id, agent_name, scene="default", bus=None):
        self.bus = bus or MessageBus()
        # ...
```

- [ ] **Step 2: Startup wiring** (in `agent_loop.py`, `entry_manager.py`)

The bus is created once at application startup and passed to all components.

---

### Task 7: Tests

- [ ] **Step 1: `tests/test_bus.py`**

Test publish/subscribe, message delivery, queue draining.

- [ ] **Step 2: Run full suite**

```bash
python3 -m pytest tests/ -v --ignore=tests/test_agent_loop.py --ignore=tests/test_memory_hierarchy.py --ignore=tests/test_per_user_dream.py --ignore=tests/test_web_auth.py
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/message.py py-agent/bus.py py-agent/channel.py py-agent/mailbox.py py-agent/scene_router.py py-agent/heartbeat.py py-agent/agent_runner.py channels/*.py tests/test_bus.py docs/superpowers/specs/*bus* docs/superpowers/plans/*bus*
git commit -m "refactor: replace polling with event-driven message bus"
```
