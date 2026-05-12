# Chat Performance Fix Design

**Date:** 2026-05-06
**Goal:** Fix frontend chat page slowness when conversing with agents — messages appear with noticeable delay.

## Root Cause Summary

Investigation revealed three independent issues stacked together:

1. **WS event type mismatch (bug):** Backend sends `WsEvent { event: "task_completed", ... }` serialized to `{"event": "task_completed", ...}`, but frontend `LiveUpdatesContext.tsx` only checks `switch (data.type)` — `data.type` is always `undefined`. Agent reply completion events are **silently dropped**, forcing the frontend to wait for the 5-second polling interval.

2. **No optimistic updates:** `Chat.tsx` `sendMessage()` uses `await chatApi.sendMessage()` + `invalidateQueries()` — the user's own message doesn't appear until the POST round-trip completes AND a GET refetch finishes.

3. **No streaming/progress:** Agent runs full ReAct loop (up to 20 iterations of LLM calls + tool executions) before returning a single JSON-RPC response. Frontend shows nothing during this time — user can't tell if agent is working or stuck.

---

## Fix 1: WebSocket Event Handling

### Problem
- Rust `dispatch/engine.rs:133-139` sends `WsEvent { event: "task_completed", ... }`
- Frontend `LiveUpdatesContext.tsx:43` does `switch (data.type)` — only handles `"agent.status"`, `"message.new"`, `"dispatch.update"`
- No code in the codebase emits a `"message.new"` event; the string only exists in the frontend handler

### Solution
Add a fallthrough handler in `LiveUpdatesContext.tsx` for backend event types. The Rust `WsEvent` struct serializes its `event` field — check `data.event` in addition to `data.type`:

```typescript
// Check both .type and .event for compatibility
const eventType = data.type || data.event
switch (eventType) {
    // ... existing cases ...
    case "task_completed":
    case "task_failed":
        qc.invalidateQueries({ queryKey: ["chat-groups"] })
        qc.invalidateQueries({ queryKey: ["chat-messages"] })
        break
}
```

Also remove `refetchInterval: 5000` from the messages query — rely on WS events for updates. Add `refetchInterval: 15000` as a fallback (in case WS disconnects).

### Files Changed
- `web-ui/src/context/LiveUpdatesContext.tsx` — ~10 lines

---

## Fix 2: Optimistic Updates

### Problem
`Chat.tsx:127-133`:
```typescript
async function sendMessage() {
    if (!selectedGroup || !message.trim()) return
    await chatApi.sendMessage(selectedGroup, message.trim())  // blocks here
    setMessage("")
    queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedGroup] })
    queryClient.invalidateQueries({ queryKey: ["chat-groups"] })
}
```

### Solution
Insert a provisional message into the React Query cache before the POST:

```typescript
async function sendMessage() {
    if (!selectedGroup || !message.trim()) return
    const content = message.trim()
    setMessage("")

    // Optimistic insert
    queryClient.setQueryData(["chat-messages", selectedGroup],
        (old: { messages: ChatMessage[] } | undefined) => ({
            messages: [...(old?.messages ?? []), {
                from: "admin",
                content,
                timestamp: new Date().toISOString(),
                mentions: parseMentions(content),
            }],
        })
    )

    await chatApi.sendMessage(selectedGroup, content)
    queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedGroup] })
    queryClient.invalidateQueries({ queryKey: ["chat-groups"] })
}
```

### Files Changed
- `web-ui/src/pages/Chat.tsx` — ~25 lines

---

## Fix 3: Agent Streaming

### Architecture
```
Python Agent (agent_runtime.py)                     Rust                           Frontend
──────────────────────────────                      ────                           ────────
agent_loop.run(                                      agent/process.rs:
  on_progress=write_line,                             call_stream() →
  on_tool=write_line,                   stdout line   读取每一行
  on_reasoning=write_line,             ─────────→     ├─ JSON-RPC 响应行 → 正常返回
)                                                      └─ {"type":"progress",...} 行
                                                        → WS 广播 dispatch/engine.rs
                                                            │
                                                   LiveUpdatesContext.tsx
                                                        │
                                                   Chat.tsx shows progress
```

### Protocol
Agent writes streaming lines to stdout **before** the final JSON-RPC response line. Rust differentiates them by checking for the `"jsonrpc"` key:

```jsonl
{"type":"progress","content":"Building system prompt..."}
{"type":"progress","content":"Calling LLM (iteration 1)..."}
{"type":"tool","name":"web_search","input":"...","status":"start"}
{"type":"tool","name":"web_search","input":"...","status":"done","result":"..."}
{"type":"reasoning","content":"The user is asking about..."}
{"type":"progress","content":"Calling LLM (iteration 2)..."}
{"jsonrpc":"2.0","id":"uuid","result":{"content":"Final answer here","iterations":2}}
```

- Lines with `"jsonrpc"` key → standard JSON-RPC response (final result)
- Lines with `"type"` key → stream event, forwarded to WS

### Changes

#### Python: `agent_runtime.py` (~20 lines)
- Add `write_progress`, `write_tool`, `write_reasoning` helper functions that write JSON lines to stdout
- Pass these as `on_progress`, `on_tool`, `on_reasoning` callbacks to `agent_loop.run()`
- Write stream `{"type":"progress|tool|reasoning",...}` lines during execution, then the final `{"jsonrpc":"2.0","id":"...","result":{...}}` line

#### Rust: `agent/process.rs` (~40 lines)
- Add `call_stream()` method that:
  1. Writes JSON-RPC request to stdin (same as before)
  2. Reads lines from stdout in a loop
  3. Lines with `"type"` key → forward through a `mpsc::Sender` callback as stream events
  4. Lines with `"jsonrpc"` key → final JSON-RPC response, parse and return result

#### Rust: `agent/manager.rs` (~10 lines)
- Add `call_agent_stream()` that returns a receiver for streaming events

#### Rust: `dispatch/engine.rs` (~30 lines)
- Modify `process_task` to accept streaming from the agent
- For each stream event: broadcast via `ws_tx` with event types:
  - `WsEvent { event: "stream_progress", ... }`
  - `WsEvent { event: "stream_tool", ... }`
  - `WsEvent { event: "stream_reasoning", ... }`
- On final result: proceed as before (insert_agent_reply, send task_completed)

#### Frontend: `LiveUpdatesContext.tsx` (~15 lines)
- Add handling for `"stream_progress"`, `"stream_tool"`, `"stream_reasoning"` events
- Store streaming state in a `Map<string, TaskStreamState>` (task_uuid → live state)

#### Frontend: `Chat.tsx` (~30 lines)
- For messages where the agent is still processing (no content yet), show a streaming indicator:
  - Progress text ("Calling LLM iteration 2/20...")
  - Tool call indicator ("🔧 web_search: searching...")
  - Reasoning/thinking text
  - Typing dots animation
- When `task_completed` fires, remove the streaming indicator and show the final message

### WebSocket Events Added
| Event | Payload | Meaning |
|-------|---------|---------|
| `stream_progress` | `{ task_uuid, content }` | Agent status update |
| `stream_tool` | `{ task_uuid, name, input, status, result }` | Tool lifecycle event |
| `stream_reasoning` | `{ task_uuid, content }` | LLM reasoning/thinking |

---

## Migration: Polling → WS-driven

Remove `refetchInterval: 5000` from the messages query. Add a fallback:

```typescript
refetchInterval: (query) => {
    // Fallback: 15s poll in case WS disconnects
    if (!navigator.onLine) return false
    return 15000
}
```

This ensures WS is the primary update mechanism, with polling as a safety net.

---

## Testing

### WS Event Fix
1. Open frontend chat, send a message to an agent
2. Wait for agent to respond (check Rust logs for "task completed")
3. Verify message appears within 1-2 seconds of completion (not 5s)

### Optimistic Update
1. Send a message in chat
2. Observe message appears in the UI immediately (before POST returns)
3. After POST + refetch, verify no duplicates or ordering issues

### Streaming
1. Send a message to an agent with a long-running task
2. Observe progress indicators in the UI during processing
3. Verify tool calls appear and resolve
4. Verify final message replaces streaming indicators

---

## Scope

This spec is focused. It does NOT include:
- Per-token text streaming (agent types out each token — that's a larger effort on top of this)
- Message editing or reactions
- Voice/video chat
- Offline message queue
