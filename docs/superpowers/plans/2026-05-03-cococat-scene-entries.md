# Scene Entry System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Build a multi-entry system where scenes can have pluggable channels (WeChat, Web API, etc.) for external users to send messages into scenes.

**Architecture:** Channel base class + unified ChatMessage format. Each channel implements `start()` and `send()`. Messages route to `scenes/{scene}/users/{user}/history.jsonl` for scene-level user isolation. Built-in `web_api` channel serves as the default ready-to-use entry.

---

## File Structure

```
Cococlaw/
├── py-agent/
│   ├── channel.py                 # NEW: Channel base class + ChatMessage
│   ├── channels/
│   │   ├── __init__.py
│   │   └── web_api.py            # NEW: HTTP API channel
│   └── scene_router.py           # NEW: routes entry messages to scene storage
├── scenes/
│   └── customer-service/         # NEW: demo scene with entry config
│       ├── scene.json            # scene metadata + entries config
│       ├── CONTEXT.md
│       ├── skills/manifest.json
│       ├── config.json           # post-import config items
│       └── users/                # per-user conversation isolation
├── web/
│   └── main.py                   # MODIFIED: add scene chat API
```

---

### Task 1: Channel base class + ChatMessage

**Files:**
- Create: `py-agent/channel.py`

- [ ] **Step 1: Create channel.py**

```python
"""Channel base class and unified message format (CowAgent pattern)."""
from datetime import datetime
import json


class ChatMessage:
    """Unified message format across all channels."""
    def __init__(self, channel_type="", scene_id="", user_id="",
                 content="", msg_type="text", msg_id="", timestamp=None):
        self.channel_type = channel_type
        self.scene_id = scene_id
        self.user_id = user_id
        self.content = content
        self.msg_type = msg_type       # text, image, voice
        self.msg_id = msg_id or str(datetime.now().timestamp())
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self):
        return {
            "channel_type": self.channel_type,
            "scene_id": self.scene_id,
            "user_id": self.user_id,
            "content": self.content,
            "msg_type": self.msg_type,
            "msg_id": self.msg_id,
            "timestamp": self.timestamp,
        }


class Channel:
    """Base class for scene entry channels.

    Subclasses must set channel_type and implement start() and send().
    """
    channel_type = ""

    def __init__(self):
        self.scene_id = ""
        self.on_message = None  # Callback: func(message: ChatMessage)

    def start(self, scene_id: str, config: dict):
        """Start listening for incoming messages.
        
        When a message arrives, wrap it in ChatMessage and call
        self.on_message(msg). Subclasses must implement this.
        """
        self.scene_id = scene_id
        raise NotImplementedError

    def send(self, reply: str, user_id: str):
        """Send a reply to a specific user through this channel."""
        raise NotImplementedError
```

- [ ] **Step 2: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from channel import Channel, ChatMessage; m = ChatMessage(channel_type='test', scene_id='s1', user_id='u1', content='hello'); print('msg ok:', m.content)"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/channel.py
git commit -m "feat: add Channel base class and ChatMessage format"
```

---

### Task 2: web_api channel

**Files:**
- Create: `py-agent/channels/__init__.py`
- Create: `py-agent/channels/web_api.py`

- [ ] **Step 1: Create channels package**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\py-agent\channels" | Out-Null
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\py-agent\channels\__init__.py" | Out-Null
```

- [ ] **Step 2: Create web_api.py**

```python
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
        """For web_api, replies are returned via HTTP response.
        This method logs the reply for pickup by the API handler.
        """
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "scenes", self.scene_id, "users", user_id, "replies.jsonl"
        )
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        entry = {"reply": reply, "timestamp": __import__("datetime").datetime.now().isoformat()}
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def receive_message(self, user_id: str, content: str) -> ChatMessage:
        """Called by the HTTP API handler when a message arrives."""
        msg = ChatMessage(
            channel_type="web_api",
            scene_id=self.scene_id,
            user_id=user_id,
            content=content,
        )
        return msg
```

- [ ] **Step 3: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from channels.web_api import WebApiChannel; ch = WebApiChannel(); ch.start('test-scene', {}); msg = ch.receive_message('user1', 'hello'); print('web_api msg ok:', msg.content)"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/channels/
git commit -m "feat: add WebApi channel for HTTP entry"
```

---

### Task 3: Scene router — message → scene storage → agent

**Files:**
- Create: `py-agent/scene_router.py`

- [ ] **Step 1: Create scene_router.py**

```python
"""Routes entry messages to scene-level user storage."""
import os
import json
from datetime import datetime


def store_message(scene_id: str, user_id: str, msg_dict: dict):
    """Store a message in scenes/{scene_id}/users/{user_id}/history.jsonl."""
    history_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "scenes", scene_id, "users", user_id
    )
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
    history_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "scenes", scene_id, "users", user_id, "history.jsonl"
    )
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
```

- [ ] **Step 2: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from scene_router import store_message, get_history; store_message('test-scene', 'user1', {'content':'hello','direction':'incoming','channel_type':'web_api'}); h = get_history('test-scene', 'user1'); print('history ok:', len(h) > 0)"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/scene_router.py
git commit -m "feat: add scene router for per-user message storage"
```

---

### Task 4: Demo scene with entry config + Web API endpoint

**Files:**
- Create: `scenes/customer-service/scene.json`
- Create: `scenes/customer-service/CONTEXT.md`
- Create: `scenes/customer-service/skills/manifest.json`
- Create: `scenes/customer-service/config.json`
- Modify: `web/main.py`

- [ ] **Step 1: Create demo scene**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\scenes\customer-service\skills" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\scenes\customer-service\users" | Out-Null
```

`scenes/customer-service/scene.json`:
```json
{
  "scene_id": "customer-service",
  "title": "智能客服",
  "version": "1.0",
  "description": "Customer service scene with multi-entry support",
  "entries": [
    {
      "channel": "web_api",
      "config": { "endpoint": "/api/scenes/customer-service/chat" },
      "after_import": "ready"
    }
  ],
  "config_after_import": {
    "mounted_kbs": [],
    "assigned_agents": { "min": 1, "current": [] }
  }
}
```

`scenes/customer-service/CONTEXT.md`:
```markdown
# Customer Service Scene

You are a customer service agent. Respond politely and helpfully.

## Guidelines
- Be professional and courteous
- Answer questions based on the knowledge base
- Escalate complex issues to a human if needed
- Keep responses concise
```

`scenes/customer-service/skills/manifest.json`:
```json
{
  "env_skills": ["user_memory"]
}
```

`scenes/customer-service/config.json`:
```json
{
  "mounted_kbs": [],
  "assigned_agents": [],
  "status": "pending_config"
}
```

- [ ] **Step 2: Add scene chat API to web/main.py**

Read `web/main.py` and add after the existing endpoints:

```python
import json
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

# ... existing code ...

@app.post("/api/scenes/{scene_id}/chat")
async def scene_chat(scene_id: str, request: Request):
    """Entry point for external users to send messages to a scene."""
    body = await request.json()
    user_id = body.get("user_id", "anonymous")
    content = body.get("content", "")

    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    # Store incoming message
    from scene_router import store_message
    store_message(scene_id, user_id, {
        "content": content,
        "direction": "incoming",
        "channel_type": "web_api",
    })

    # Read conversation history for context
    from scene_router import get_history
    history = get_history(scene_id, user_id, limit=10)

    # Build context for agent
    prompt = f"[User {user_id}] {content}\n\nRecent history:\n"
    for h in history[:-1]:
        prompt += f"[{h['direction']}] {h['content']}\n"

    # For now, return a confirmation. Agent processing will be wired next.
    return JSONResponse({
        "reply": f"Message received by scene '{scene_id}'. Content: {content[:100]}",
        "user_id": user_id,
    })


@app.get("/api/scenes/{scene_id}/users/{user_id}/history")
def get_user_history(scene_id: str, user_id: str, limit: int = 20):
    """API to read a user's conversation history in a scene."""
    sys.path.insert(0, str(BASE_DIR / "py-agent"))
    from scene_router import get_history
    history = get_history(scene_id, user_id, limit=limit)
    return {"history": history}
```

- [ ] **Step 3: Test**

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
python -m uvicorn web.main:app --port 8080 &
Start-Sleep -Seconds 2

# Send a message to the scene
Invoke-RestMethod -Uri "http://localhost:8080/api/scenes/customer-service/chat" -Method Post -Body '{"user_id":"user123","content":"Hello, I need help with my order"}' -ContentType "application/json"
```

- [ ] **Step 4: Commit**

```bash
git add scenes/customer-service/ web/main.py
git commit -m "feat: add demo scene with web API entry and user history"
```

---

### Task 5: Wire agent processing into scene messages

**Files:**
- Modify: `web/main.py`
- Modify: `py-agent/scene_router.py`

- [ ] **Step 1: Add agent processing to scene chat**

In `web/main.py`, update the scene_chat endpoint to actually process the message through an agent. Read the scene's config to find the assigned agent, then route the message for processing.

```python
@app.post("/api/scenes/{scene_id}/chat")
async def scene_chat(scene_id: str, request: Request):
    body = await request.json()
    user_id = body.get("user_id", "anonymous")
    content = body.get("content", "")

    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    # Store incoming message
    import sys as _sys
    _sys.path.insert(0, str(BASE_DIR / "py-agent"))
    from scene_router import store_message, get_history

    store_message(scene_id, user_id, {
        "content": content, "direction": "incoming", "channel_type": "web_api",
    })

    # Load scene context and history
    history = get_history(scene_id, user_id, limit=10)
    scene_dir = BASE_DIR / "scenes" / scene_id
    context = ""
    ctx_path = scene_dir / "CONTEXT.md"
    if ctx_path.exists():
        context = ctx_path.read_text(encoding="utf-8")

    history_text = "\n".join([f"[{h['direction']}] {h['content']}" for h in history])

    # Route to agent via JSON-RPC
    import subprocess, json as _json
    agent_script = str(BASE_DIR / "py-agent" / "agent_runtime.py")
    prompt = f"{context}\n\n## Conversation\n{history_text}\n\n[user] {content}\n\nRespond to the user's message."
    task = _json.dumps({"jsonrpc": "2.0", "method": "task", "params": {"prompt": prompt}, "id": 1})

    try:
        result = subprocess.run(
            ["python", "-u", agent_script],
            input=task, capture_output=True, text=True, timeout=60,
        )
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line:
                try:
                    resp = _json.loads(line)
                    reply_text = resp.get("result", {}).get("content", "") or resp.get("error", {}).get("message", "No response")
                    break
                except _json.JSONDecodeError:
                    continue
        else:
            reply_text = result.stdout.strip() or "(no response)"
    except subprocess.TimeoutExpired:
        reply_text = "Agent processing timed out."
    except Exception as e:
        reply_text = f"Agent error: {e}"

    # Store reply
    store_message(scene_id, user_id, {
        "content": reply_text, "direction": "outgoing", "channel_type": "web_api",
    })

    return JSONResponse({"reply": reply_text, "user_id": user_id})
```

- [ ] **Step 2: Test end-to-end**

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"

# Restart web server and test
Invoke-RestMethod -Uri "http://localhost:8080/api/scenes/customer-service/chat" -Method Post -Body '{"user_id":"user123","content":"I need help with my order #12345"}' -ContentType "application/json"
```

- [ ] **Step 3: Commit**

```bash
git add web/main.py
git commit -m "feat: wire agent processing into scene chat API"
```
