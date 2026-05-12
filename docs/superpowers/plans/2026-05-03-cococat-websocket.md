# WebSocket Real-Time Updates Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Add WebSocket endpoint for real-time updates in the management panel.

**Architecture:** Single `/ws` endpoint on FastAPI. WebSocketManager broadcasts agent_status, chat_message, and heartbeat events.

---

### Task 1: WebSocket endpoint + broadcast

**Files:**
- Modify: `web/main.py`

- [ ] **Step 1: Update web/main.py**

Read current `C:\Users\12991\Desktop\Cococlaw\web\main.py`. Add WebSocket support.

At the top, add import:
```python
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
```

Add a WebSocket manager class before the app endpoints:

```python
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, event: str, data: dict):
        payload = json.dumps({"event": event, "data": data})
        stale = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()
```

Add the WebSocket endpoint before the dashboard HTML route:

```python
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # Keep connection open
    except WebSocketDisconnect:
        manager.disconnect(ws)
```

Add heartbeat task:

```python
@app.on_event("startup")
async def start_heartbeat():
    asyncio.create_task(_heartbeat_loop())

async def _heartbeat_loop():
    while True:
        await asyncio.sleep(10)
        await manager.broadcast("heartbeat", {"timestamp": __import__("datetime").datetime.now().isoformat()})
```

- [ ] **Step 2: Wire chat_log and agent events to broadcast**

In `scene_chat` and `wechat_webhook` endpoints, after storing messages, add:

```python
    await manager.broadcast("chat_message", {
        "channel": channel_type,
        "content": content[:200],
        "direction": "incoming",
    })
    # ...after reply:
    await manager.broadcast("chat_message", {
        "channel": channel_type,
        "content": reply_text[:200],
        "direction": "outgoing",
    })
```

Note: `scene_chat` is async already. For `wechat_webhook`, make the broadcast call but don't block on it if the function is sync.

Actually, simplify: the broadcast can be added later. For MVP, just the WebSocket endpoint + heartbeat + a dashboard HTML page that connects to it.

- [ ] **Step 3: Add WebSocket test page to dashboard**

At the bottom of the dashboard HTML (before `</body>`), add:

```html
<script>
const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  const el = document.getElementById('ws-log');
  el.innerHTML = `<div>${msg.event}: ${JSON.stringify(msg.data).substring(0,100)}</div>` + el.innerHTML;
};
</script>
<div id="ws-log" class="mt-6 bg-gray-100 p-4 text-xs max-h-40 overflow-y-auto" style="font-family:monospace">Connecting...</div>
```

- [ ] **Step 4: Test**

```bash
pip install websockets -q
```

Start server and verify WebSocket connection:
```powershell
# Start server, then test from another terminal:
python -c "import asyncio, websockets; async def t(): async with websockets.connect('ws://localhost:8081/ws') as ws: print(await asyncio.wait_for(ws.recv(), timeout=5)); asyncio.run(t())"
```

- [ ] **Step 5: Commit**

```bash
git add web/main.py
git commit -m "feat: add WebSocket endpoint with heartbeat and dashboard display"
```
