# Message Bus Redesign

**Goal:** Replace the current polling-based message delivery (heartbeat polls mailbox + chat_reader every 5 minutes) with an event-driven message bus that delivers messages in real-time.

**Problems solved:**
- 5-minute polling delay → instant delivery
- Two uncoordinated mailbox write paths → single consumer
- Channel message history not recorded in scene_router → automatic
- Agent has no way to know when new messages arrive → event-driven

## Architecture

```
                     ┌──────────────────┐
                     │   MessageBus     │
                     │  (queue.Queue)   │
                     └──┬───────────┬──┘
                        │ inbound   │ outbound
          ┌─────────────┼───────────┼──────────────┐
          │             │           │               │
          ▼             ▼           ▼               ▼
   Channels      Mailbox      SceneRouter      AgentLoop
   (publish)   (persist)     (record)        (process → publish)
          │             ▲           ▲               │
          └─────────────┴───────────┴───────────────┘
                       outbound
```

## Message Types

```python
@dataclass
class InboundMessage:
    channel: str          # "telegram", "feishu", "mailbox", "chat", etc.
    source: str           # sender identifier
    content: str
    agent_id: str         # target agent
    scene_id: str = "default"
    metadata: dict = field(default_factory=dict)

@dataclass  
class OutboundMessage:
    channel: str
    target: str           # recipient identifier
    content: str
    metadata: dict = field(default_factory=dict)
```

## MessageBus

- `publish_inbound(msg)` → put in inbound queue, notify agent
- `publish_outbound(msg)` → put in outbound queue
- `subscribe_inbound(handler)` → register consumer for inbound messages
- `subscribe_outbound(handler)` → register consumer for outbound messages

## Consumers

| Consumer | Subscribes to | Action |
|----------|--------------|--------|
| MailboxPersister | inbound | Save to `inbox.jsonl` (persistence) |
| SceneRouter | inbound + outbound | Record scene history |
| AgentWakeup | inbound | Signal heartbeat to wake agent |
| AgentLoop | inbound | Process message |
| ChannelDispatcher | outbound | Send response back to user |

## Changes Summary

| File | Action | Change |
|------|--------|--------|
| `py-agent/message.py` | Create | InboundMessage, OutboundMessage types |
| `py-agent/bus.py` | Create | MessageBus class |
| `py-agent/channel.py` | Modify | Remove on_message callback, bus-based |
| `py-agent/mailbox.py` | Modify | Add bus consumer for persistence |
| `py-agent/chat_reader.py` | Modify | Publish chat messages to bus |
| `py-agent/scene_router.py` | Modify | Bus consumer for scene history |
| `py-agent/agent_status.py` | Modify | Bus consumer for status |
| `py-agent/heartbeat.py` | Modify | Remove polling, consume bus events |
| `py-agent/agent_loop.py` | Modify | Consume from bus, publish outbound |
| `web/entry_manager.py` | Modify | Register channels with bus |
| `channels/*.py` | Modify | Publish to bus instead of direct file write |
