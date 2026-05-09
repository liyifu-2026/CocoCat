# Scene Entry System Design

## Problem
Scenes are currently passive — agents must be explicitly told to work in a scene. There's no way for external users to send messages into a scene. CocoCat needs a multi-entry system where different channels (WeChat, Web API, etc.) can be plugged into scenes, routing messages to the right scene and user.

## Architecture

### Scene Entry Model
Each scene declares which entry channels it uses. Entries are either "ready" (import-and-use) or "setup" (need credential configuration after import).

```
scene-package/
├── scene.json              # Metadata, entries config
├── CONTEXT.md              # Scene prompt
├── skills/                 # Env skills (including user_memory)
├── config.json             # Post-import config items (KBs, agents)
└── entries/                # Per-channel config files (generated on import)
    ├── wechat.json
    └── web_api.json
```

### Channel Interface
```python
class Channel:
    channel_type: str

    def start(self, scene_id, config):
        """Start listening. Call self.on_message() when received."""

    def send(self, reply, user_id):
        """Send reply back through this channel."""

    def on_message(self, message):
        """Callback — called by framework when message arrives."""
```

### Unified Message Format
```python
class ChatMessage:
    msg_id: str
    channel_type: str
    scene_id: str
    user_id: str
    content: str
    msg_type: str        # "text", "image", "voice"
    timestamp: str
```

### Message Flow
```
External User → Channel.start() listening
    │
    ├── Receives raw message
    ├── Wraps into ChatMessage
    └── Calls on_message(message)
            │
            ▼
    Framework routes:
    ┌─ 1. Store to scenes/{scene_id}/users/{user_id}/history.jsonl
    ├─ 2. Pass to scene's agent for processing
    └─ 3. Agent responds → Channel.send(reply, user_id)
```

### Entry Config (in scene.json)
```json
{
  "entries": [
    {
      "channel": "wechat",
      "config": { "app_id": "", "token": "" },
      "after_import": "setup"
    },
    {
      "channel": "web_api",
      "config": { "endpoint": "/api/scenes/{scene_id}/chat" },
      "after_import": "ready"
    }
  ]
}
```

### Scene-level User Memory Isolation
- `scenes/{scene_id}/users/{user_id}/history.jsonl` — per-user-per-scene conversation log
- Any agent assigned to this scene can read/write this log
- Data never leaks into agent's personal memory or other scenes

## Implementation Order
1. Channel base class + ChatMessage
2. web_api channel (built-in, always available)
3. Scene entry config in scene.json
4. Message routing (entry → scene → agent)
5. Scene package export/import
6. Additional channels (wechat, etc.)
