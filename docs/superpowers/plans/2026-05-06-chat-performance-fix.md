# Chat Performance Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix frontend chat page slowness — eliminate the 5-second polling delay, add instant optimistic updates for sent messages, and stream agent progress indicators to the UI.

**Architecture:** Three independent layers of fix — (1) align WS event types so agent completion triggers immediate message refresh, (2) add optimistic cache updates so user messages appear instantly, (3) connect Python agent's existing progress callbacks through Rust to the frontend via WebSocket for real-time progress display.

**Tech Stack:** React + TypeScript (Vite), Rust (Axum/Tokio), Python (agent subprocess), SQLite

---

## File Map

| File | Responsibility |
|------|---------------|
| `web-ui/src/context/LiveUpdatesContext.tsx` | WS event routing |
| `web-ui/src/pages/Chat.tsx` | Optimistic updates, streaming UI |
| `py-agent/agent_runtime.py` | Write stream lines to stdout during agent execution |
| `src/agent/stream_event.rs` | `StreamEvent` data type |
| `src/agent/process.rs` | `call_stream()` — reads agent stdout, forwards events to WS in real-time |
| `src/agent/manager.rs` | `call_agent_stream()` — streaming agent call |
| `src/dispatch/engine.rs` | Streaming dispatch, WsEvent extended |

---

### Task 1: Fix WS Event Type Mismatch

**Files:**
- Modify: `web-ui/src/context/LiveUpdatesContext.tsx:40-58`

The backend sends `WsEvent` serialized as `{"event": "task_completed", ...}` with no `type` field. The frontend only checks `data.type`. Fix by checking both `data.type` and `data.event`.

- [ ] **Step 1: Add `task_completed`/`task_failed` handler**

In `LiveUpdatesContext.tsx`, replace the `onmessage` handler. Change:

```typescript
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        switch (data.type) {
          case "agent.status":
            qc.invalidateQueries({ queryKey: ["agents"] })
            if (data.status === "error") {
              dedupedToast(`agent-${data.agent_id}`, `Agent ${data.agent_id} encountered an error`)
            }
            break
          case "message.new":
            qc.invalidateQueries({ queryKey: ["chat-groups"] })
            qc.invalidateQueries({ queryKey: ["chat-messages"] })
            dedupedToast("message-new", `New message from ${data.from ?? "unknown"}`)
            break
          case "dispatch.update":
            qc.invalidateQueries({ queryKey: ["dispatches"] })
            break
        }
      } catch (err) {
        console.warn("LiveUpdates: failed to parse message", err)
      }
    }
```

To:

```typescript
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const eventType = data.type || data.event
        switch (eventType) {
          case "agent.status":
            qc.invalidateQueries({ queryKey: ["agents"] })
            if (data.status === "error") {
              dedupedToast(`agent-${data.agent_id}`, `Agent ${data.agent_id} encountered an error`)
            }
            break
          case "message.new":
            qc.invalidateQueries({ queryKey: ["chat-groups"] })
            qc.invalidateQueries({ queryKey: ["chat-messages"] })
            dedupedToast("message-new", `New message from ${data.from ?? "unknown"}`)
            break
          case "dispatch.update":
            qc.invalidateQueries({ queryKey: ["dispatches"] })
            break
          case "task_completed":
          case "task_failed":
            qc.invalidateQueries({ queryKey: ["chat-groups"] })
            qc.invalidateQueries({ queryKey: ["chat-messages"] })
            break
        }
      } catch (err) {
        console.warn("LiveUpdates: failed to parse message", err)
      }
    }
```

- [ ] **Step 2: Reduce polling interval**

In `Chat.tsx`, on the messages query, change:

```typescript
    refetchInterval: 5000,
```

To:

```typescript
    refetchInterval: 15000,
```

- [ ] **Step 3: Verify**

Run both frontend and backend. Send a message to an agent. Check Rust logs for `"task completed"`. Verify the agent's reply appears in the chat UI within 1-2 seconds of that log line. Check DevTools Network tab — `/messages?limit=100` requests now fire every 15s instead of every 5s.

---

### Task 2: Add Optimistic Updates for Sent Messages

**Files:**
- Modify: `web-ui/src/pages/Chat.tsx:127-133`

The user's own message doesn't appear until POST round-trip + GET refetch completes. Insert it into the cache immediately on send.

- [ ] **Step 1: Modify `sendMessage()`**

In `Chat.tsx`, change `sendMessage()` from:

```typescript
  async function sendMessage() {
    if (!selectedGroup || !message.trim()) return
    await chatApi.sendMessage(selectedGroup, message.trim())
    setMessage("")
    queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedGroup] })
    queryClient.invalidateQueries({ queryKey: ["chat-groups"] })
  }
```

To:

```typescript
  async function sendMessage() {
    if (!selectedGroup || !message.trim()) return
    const content = message.trim()
    setMessage("")

    queryClient.setQueryData(["chat-messages", selectedGroup],
      (old: { messages: ChatMessage[] } | undefined) => ({
        messages: [...(old?.messages ?? []), {
          from: "admin",
          content,
          timestamp: new Date().toISOString(),
          mentions: [],
        }],
      })
    )

    await chatApi.sendMessage(selectedGroup, content)
    queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedGroup] })
    queryClient.invalidateQueries({ queryKey: ["chat-groups"] })
  }
```

- [ ] **Step 2: Verify**

Send a message. The bubble appears instantly. After POST + refetch, no duplicates.

---

### Task 3: Python Agent Streaming Output

**Files:**
- Modify: `py-agent/agent_runtime.py:62-94`

The agent currently writes a single JSON-RPC response line to stdout. For the `"chat"` method, write streaming progress lines first, then the final JSON-RPC response.

- [ ] **Step 1: Add streaming helpers and modify `main()`**

In `agent_runtime.py`, add these helper functions at module level:

```python
def _write_stream(etype: str, **kwargs):
    data = {"type": etype}
    data.update(kwargs)
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()
```

Replace the `for line in sys.stdin:` loop in `main()`:

```python
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request = None
        req_id = None
        try:
            request = json.loads(line)
            req_id = request.get("id")

            if request.get("method") == "chat":
                params = request.get("params", {})
                content = params.get("content", "")
                messages = params.get("messages", [])

                def on_progress(msg):
                    _write_stream("progress", content=msg)
                def on_tool(name, input_data, status, result=""):
                    _write_stream("tool", name=name,
                        input=str(input_data)[:500], status=status,
                        result=str(result)[:500])
                def on_reasoning(msg):
                    if msg:
                        _write_stream("reasoning", content=msg)

                result = agent_loop.run(
                    content,
                    user_id=params.get("user_id", ""),
                    on_progress=on_progress,
                    on_tool=on_tool,
                    on_reasoning=on_reasoning,
                )
                response = {"jsonrpc": "2.0", "result": result, "id": req_id}
            else:
                result = handle_request(request, agent_loop=agent_loop)
                response = {"jsonrpc": "2.0", "result": result, "id": req_id}
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None,
            }
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
```

- [ ] **Step 2: Verify streaming output**

```bash
echo '{"jsonrpc":"2.0","id":"1","method":"chat","params":{"content":"hello"}}' | python3 py-agent/agent_runtime.py --agent-id test
```

Expected output: zero or more `{"type":"progress",...}` lines, then `{"jsonrpc":"2.0","id":"1","result":{...}}` as the final line.

---

### Task 4: Rust `StreamEvent` Type + Extend `WsEvent`

**Files:**
- Create: `src/agent/stream_event.rs`
- Modify: `src/agent/mod.rs`
- Modify: `src/dispatch/engine.rs`

- [ ] **Step 1: Create `src/agent/stream_event.rs`**

```rust
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct StreamEvent {
    pub event_type: String,
    pub content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<String>,
}

impl StreamEvent {
    pub fn progress(content: String) -> Self {
        Self { event_type: "stream_progress".into(), content, name: None, input: None, status: None, result: None }
    }
    pub fn tool(name: String, input: String, status: String, result: String) -> Self {
        Self { event_type: "stream_tool".into(), content: String::new(), name: Some(name), input: Some(input), status: Some(status), result: Some(result) }
    }
    pub fn reasoning(content: String) -> Self {
        Self { event_type: "stream_reasoning".into(), content, name: None, input: None, status: None, result: None }
    }
}
```

- [ ] **Step 2: Register module**

In `src/agent/mod.rs`, add `pub mod stream_event;`

- [ ] **Step 3: Extend `WsEvent`**

In `src/dispatch/engine.rs`, add a `stream_event` field:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsEvent {
    pub event: String,
    pub task_uuid: String,
    pub status: String,
    pub result: Option<Value>,
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stream_event: Option<crate::agent::stream_event::StreamEvent>,
}
```

- [ ] **Step 4: Verify it compiles**

```bash
cargo check 2>&1 | head -30
```

---

### Task 5: Rust `AgentProcess::call_stream()`

**Files:**
- Modify: `src/agent/process.rs`

Add a `call_stream()` method that reads stdout lines in a loop. For stream lines (with `"type"` key), it forwards a `WsEvent` to the broadcast channel in real-time. For the final JSON-RPC response line, it returns the result.

This works because `tokio::sync::broadcast::Sender` is `Send + Sync`, so it can be used from a blocking thread.

- [ ] **Step 1: Add `call_stream()` to `AgentProcess`**

In `src/agent/process.rs`, add after the existing `call()` method:

```rust
    pub fn call_stream(
        &mut self,
        method: &str,
        params: Value,
        timeout_secs: u64,
        ws_tx: &tokio::sync::broadcast::Sender<WsEvent>,
        task_uuid: &str,
    ) -> Result<Value, String> {
        let request = JsonRpcRequest {
            jsonrpc: "2.0".into(),
            id: uuid::Uuid::new_v4().to_string(),
            method: method.into(),
            params,
        };

        let request_line = serde_json::to_string(&request)
            .map_err(|e| format!("serialize request: {}", e))?;

        if let Some(ref mut stdin) = self.stdin_writer {
            writeln!(stdin, "{}", request_line)
                .map_err(|e| format!("write to stdin: {}", e))?;
            stdin.flush().map_err(|e| format!("flush stdin: {}", e))?;
        } else {
            return Err("stdin closed".to_string());
        }

        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(timeout_secs);

        loop {
            if std::time::Instant::now() > deadline {
                return Err(format!("Agent {} call timed out after {}s", self.agent_id, timeout_secs));
            }

            let remaining = deadline - std::time::Instant::now();
            let line = self.stdout_receiver
                .recv_timeout(remaining.max(std::time::Duration::from_secs(1)))
                .map_err(|e| match e {
                    mpsc::RecvTimeoutError::Timeout => {
                        format!("Agent {} call timed out", self.agent_id)
                    }
                    mpsc::RecvTimeoutError::Disconnected => {
                        "Agent stdout channel disconnected".to_string()
                    }
                })?;

            let parsed: serde_json::Value = serde_json::from_str(&line)
                .map_err(|e| format!("parse line: {} (raw: {})", e, line))?;

            if parsed.get("jsonrpc").and_then(|v| v.as_str()) == Some("2.0") {
                let response: JsonRpcResponse = serde_json::from_str(&line)
                    .map_err(|e| format!("parse JSON-RPC response: {} (raw: {})", e, line))?;
                if let Some(err) = response.error {
                    return Err(format!("Agent error: {} (code {})", err.message, err.code));
                }
                return Ok(response.result.unwrap_or(Value::Null));
            }

            if let Some(etype) = parsed.get("type").and_then(|v| v.as_str()) {
                let stream_event = match etype {
                    "progress" => Some(StreamEvent::progress(
                        parsed.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    )),
                    "tool" => Some(StreamEvent::tool(
                        parsed.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        parsed.get("input").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        parsed.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        parsed.get("result").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    )),
                    "reasoning" => Some(StreamEvent::reasoning(
                        parsed.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    )),
                    _ => None,
                };
                if let Some(se) = stream_event {
                    let ws_event = WsEvent {
                        event: se.event_type.clone(),
                        task_uuid: task_uuid.to_string(),
                        status: "streaming".into(),
                        result: None,
                        error: None,
                        stream_event: Some(se),
                    };
                    let _ = ws_tx.send(ws_event);
                }
            }
        }
    }
```

Add these imports at the top of `process.rs`:
```rust
use crate::agent::stream_event::StreamEvent;
use crate::dispatch::engine::WsEvent;
```

- [ ] **Step 2: Verify it compiles**

```bash
cargo check 2>&1 | head -30
```

---

### Task 6: Rust `AgentManager::call_agent_stream()` + `DispatchEngine` Integration

**Files:**
- Modify: `src/agent/manager.rs`
- Modify: `src/dispatch/engine.rs`

- [ ] **Step 1: Add `call_agent_stream()` to `AgentManager`**

In `src/agent/manager.rs`, add:

```rust
    pub fn call_agent_stream(
        &self,
        agent_id: &str,
        method: &str,
        params: serde_json::Value,
        timeout_secs: u64,
        ws_tx: &tokio::sync::broadcast::Sender<WsEvent>,
        task_uuid: &str,
    ) -> Result<serde_json::Value, String> {
        let mut processes = self.processes.lock()
            .map_err(|e| format!("lock error: {}", e))?;
        let process = processes.get_mut(agent_id)
            .ok_or_else(|| format!("Agent {} not found", agent_id))?;
        process.call_stream(method, params, timeout_secs, ws_tx, task_uuid)
    }
```

Add import: `use crate::dispatch::engine::WsEvent;`

- [ ] **Step 2: Modify `process_task()` in `engine.rs`**

In `src/dispatch/engine.rs`, replace the `spawn_blocking` call. Change:

```rust
    let manager = agent_manager.clone();
    let call_result = tokio::task::spawn_blocking(move || {
        manager.call_agent(&target, &method, params, 120)
    })
    .await
    .map_err(|e| format!("join error: {}", e))?;
```

To:

```rust
    let manager = agent_manager.clone();
    let ws_clone = ws_tx.clone();
    let uuid_clone = task_uuid.to_string();
    let call_result = tokio::task::spawn_blocking(move || {
        manager.call_agent_stream(&target, &method, params, 120, &ws_clone, &uuid_clone)
    })
    .await
    .map_err(|e| format!("join error: {}", e))?;
```

- [ ] **Step 3: Verify it compiles**

```bash
cargo check 2>&1 | head -30
```

---

### Task 7: Frontend Streaming Event Handling + UI

**Files:**
- Modify: `web-ui/src/context/LiveUpdatesContext.tsx`
- Modify: `web-ui/src/pages/Chat.tsx`

- [ ] **Step 1: Add streaming event handlers to `LiveUpdatesContext.tsx`**

Use a module-level Map to store stream state (shared with Chat.tsx). Add at module level:

```typescript
export type StreamState = {
  task_uuid: string
  event: string
  status: string
  stream_event?: { event_type: string; content: string; name?: string; input?: string; status?: string; result?: string }
  updatedAt: number
}
export const streamState = new Map<string, StreamState>()
export const streamListeners = new Set<() => void>()
```

Add these cases to the `switch (eventType)` block (after `task_failed`):

```typescript
          case "stream_progress":
          case "stream_tool":
          case "stream_reasoning":
            streamState.set(data.task_uuid, { ...data, updatedAt: Date.now() })
            streamListeners.forEach(fn => fn())
            break
```

- [ ] **Step 2: Add streaming indicators to `Chat.tsx`**

Add at top imports:

```typescript
import { streamState, streamListeners, type StreamState } from "@/context/LiveUpdatesContext"
```

Add near other state:

```typescript
  const [, forceRender] = useState(0)
```

Add effect to subscribe to stream updates:

```typescript
  useEffect(() => {
    const handler = () => forceRender(n => n + 1)
    streamListeners.add(handler)
    return () => { streamListeners.delete(handler) }
  }, [])
```

Add a helper to get the active streaming state for the current group:

```typescript
  function activeStreamState(): { state: StreamState; agentName: string } | null {
    if (!currentGroup || messages.length === 0) return null
    const agentId = selectedGroup?.startsWith("dm_")
      ? selectedGroup.replace("dm_", "")
      : currentGroup.members.find(m => m.agent_id !== "admin")?.agent_id
    if (!agentId) return null
    for (const s of streamState.values()) {
      if (s.status === "streaming" && s.event !== "task_completed") {
        return { state: s, agentName: agentNames[agentId] ?? agentId }
      }
    }
    return null
  }
```

After the messages loop and before `messagesEndRef`, add a streaming indicator that shows progress:

```tsx
                {(() => {
                  const stream = activeStreamState()
                  if (!stream) return null
                  const se = stream.state.stream_event
                  let label = "Processing..."
                  if (se) {
                    if (se.event_type === "stream_progress") label = se.content
                    else if (se.event_type === "stream_tool") label = `🔧 ${se.name}: ${se.input?.slice(0, 60)}`
                    else if (se.event_type === "stream_reasoning") label = "Thinking..."
                  }
                  return (
                    <div className="flex gap-2">
                      <AgentAvatar name={stream.agentName} size="sm" />
                      <div className="bg-muted rounded-lg px-3 py-2 text-sm max-w-[70%]">
                        <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1">
                          <span className="animate-pulse">●</span>
                          <span className="truncate">{label}</span>
                        </div>
                      </div>
                    </div>
                  )
                })()}
```

Clean up stale stream states on task_completed. In `LiveUpdatesContext.tsx`, add to the `task_completed`/`task_failed` case:

```typescript
          case "task_completed":
          case "task_failed":
            qc.invalidateQueries({ queryKey: ["chat-groups"] })
            qc.invalidateQueries({ queryKey: ["chat-messages"] })
            streamState.delete(data.task_uuid)
            streamListeners.forEach(fn => fn())
            break
```

- [ ] **Step 3: Verify**

Send a message to an agent. During processing, a streaming indicator should appear below the messages. After the agent responds, the indicator disappears and the real message appears.

---

### Task 8: Integration Test

- [ ] **Step 1: Full stack test**

1. Start Rust backend: `cargo run`
2. Start frontend: `cd web-ui && npm run dev`
3. Open browser to chat page
4. Send a message in a DM or channel
5. Verify:
   - Message bubble appears instantly (optimistic update)
   - Streaming indicator shows during agent processing
   - Agent reply appears promptly after completion (not delayed by polling)
6. Disconnect network briefly, verify WS reconnects and messages still arrive

- [ ] **Step 2: Check no regressions**

1. Verify non-chat methods (ping, identify, shutdown) still work via JSON-RPC
2. Verify `cargo test` passes (if any)
3. Verify `npm run build` passes (if build script exists)
