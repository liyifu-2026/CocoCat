# Streaming Support Design

**Goal:** Scene chat API streams agent response tokens in real-time via WebSocket.

**Architecture:** Agent subprocess outputs incremental JSON lines during processing. Web API reads these lines and forwards to WebSocket manager. Management panel displays live tokens.

## Protocol

Agent subprocess outputs streaming events as JSON lines:

```jsonl
{"event": "delta", "content": "Hello"}
{"event": "delta", "content": " world"}
{"event": "tool_start", "tool": "web_search", "input": "..."}
{"event": "delta", "content": " Here's what I found"}
{"event": "done", "content": "Hello world. Here's what I found..."}
```

## WebSocket Forwarding

```
scene_chat → spawn subprocess → read stdout line by line
                                    │
                               forward to WebSocket:
                               {"event": "stream_delta", "data": {"scene_id", "user_id", "delta"}}
                               {"event": "stream_end", "data": {"scene_id", "user_id", "content"}}
```

## LLM Streaming

Add `chat_stream()` method that yields content deltas as they arrive from the API.
