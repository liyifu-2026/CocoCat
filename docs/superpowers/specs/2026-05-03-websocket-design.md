# WebSocket Real-Time Updates Design

**Goal:** Add a WebSocket endpoint to the FastAPI server that pushes real-time updates to connected clients.

**Architecture:** Single `/ws` WebSocket endpoint using FastAPI's built-in WebSocket support. Server broadcasts typed JSON events to all connected clients. No authentication for local use.

## Events

| Event | Data | Trigger |
|-------|------|---------|
| `agent_status` | `{id, name, status, scene}` | Agent spawn/exit |
| `chat_message` | `{from, content, timestamp, channel}` | New chat log entry |
| `heartbeat` | `{timestamp}` | Every 10s |

## Connection Management
- Single global broadcast group
- Client disconnect → auto-removed
- Ping/pong via heartbeat

## Implementation
- Add WebSocket endpoint to `web/main.py`
- Use FastAPI's `WebSocket` + `websockets` broadcast pattern
- Manager class tracks connections
