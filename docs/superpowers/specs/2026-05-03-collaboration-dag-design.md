# Collaboration DAG Design

## Overview

Add a **task flow DAG** visualization to CocoCat showing how agents collaborate — who dispatches tasks to whom, what replies come back, and the complete task lifecycle.

## Data Flow

The data already exists in Rust's `chat/group.jsonl`. Each message has `from`, `to`, and `message_type` (`task`/`reply`/`system`). The missing piece is **pairing**: connecting a `task` message to its corresponding `reply`.

### Task ID Integration

Add `task_id` to the `ChatMessage` struct:

```rust
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub msg_id: String,
    pub task_id: Option<u64>,  // NEW — links task to reply
    pub timestamp: String,
    pub from: String,
    pub to: String,
    pub content: String,
    pub message_type: String,
}
```

In `main.rs`, `check_and_process_dispatches()` assigns a `task_id` when processing each dispatch:

```rust
use std::sync::atomic::{AtomicU64, Ordering};
static NEXT_TASK_ID: AtomicU64 = AtomicU64::new(1);

// When logging the dispatch (task):
let task_id = NEXT_TASK_ID.fetch_add(1, Ordering::Relaxed);
let msg = message_bus::ChatMessage {
    task_id: Some(task_id),
    ..message_bus::new_message("leader", &target_id, &prompt, "task")
};

// When logging the reply:
let msg = message_bus::ChatMessage {
    task_id: Some(task_id),
    ..message_bus::new_message(&target_id, "leader", &content, "reply")
};
```

## API

**New file:** `web/routes/collaboration.py`

### `GET /api/collaboration/graph`

Reads `chat/group.jsonl`, groups by `task_id`, returns DAG structure.

```python
@router.get("/api/collaboration/graph")
async def collaboration_graph(request: Request):
    chat_path = BASE_DIR / "chat" / "group.jsonl"
    if not chat_path.exists():
        return {"nodes": [], "edges": []}

    messages = []
    with open(chat_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    # Build nodes (unique agents)
    agent_ids = set()
    for m in messages:
        if m["from"] != "system":
            agent_ids.add(m["from"])
        if m["to"] != "*" and m["to"] != "system":
            agent_ids.add(m["to"])

    # Load agent display info from config
    config_path = BASE_DIR / "agents" / "config.toml"
    agent_names = {}
    if config_path.exists():
        import tomllib
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        for a in config.get("agents", []):
            agent_names[a["id"]] = a.get("name", a["id"])

    nodes = [
        {"id": aid, "label": agent_names.get(aid, aid)}
        for aid in sorted(agent_ids)
    ]

    # Build edges grouped by task_id
    tasks = {}  # task_id -> {task_msg, reply_msgs}
    for m in messages:
        tid = m.get("task_id")
        if tid is None:
            continue
        if tid not in tasks:
            tasks[tid] = {"task": None, "replies": []}
        if m["message_type"] == "task":
            tasks[tid]["task"] = m
        else:
            tasks[tid]["replies"].append(m)

    edges = []
    for tid, flow in tasks.items():
        task = flow["task"]
        if not task:
            continue
        edges.append({
            "id": f"task_{tid}",
            "from": task["from"],
            "to": task["to"],
            "task_id": tid,
            "type": "task",
            "summary": task["content"][:100],
            "timestamp": task["timestamp"],
            "replies": [
                {"from": r["from"], "content": r["content"][:200], "timestamp": r["timestamp"]}
                for r in flow["replies"]
            ],
        })

    return {"nodes": nodes, "edges": edges}
```

### `GET /api/collaboration/graph/events`

SSE or simple polling endpoint for recent activity (last 30 seconds):

```python
@router.get("/api/collaboration/graph/events")
async def recent_events(request: Request):
    """Return edges from the last 60 seconds for real-time updates."""
    chat_path = BASE_DIR / "chat" / "group.jsonl"
    if not chat_path.exists():
        return {"edges": []}

    import datetime
    cutoff = (datetime.datetime.now(datetime.timezone.utc) -
              datetime.timedelta(seconds=60)).isoformat()

    recent_edges = []
    messages = []
    with open(chat_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    for m in messages:
        if m.get("timestamp", "") >= cutoff and m["message_type"] in ("task", "reply"):
            recent_edges.append(m)

    return {"edges": recent_edges[-20:]}
```

## Frontend

**New file:** `web-ui/src/pages/Collaboration.tsx`

### DAG Rendering

Use `dagre` for layout computation + pure SVG for rendering.

```typescript
import { useEffect, useRef, useState } from "react";
import dagre from "dagre";

interface GraphNode {
  id: string;
  label: string;
}

interface GraphEdge {
  id: string;
  from: string;
  to: string;
  type: "task" | "reply";
  summary: string;
  timestamp: string;
  replies?: { from: string; content: string; timestamp: string }[];
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}
```

**Layout algorithm:**

```
dagre graph setup:
  rankdir: TB (top-to-bottom)
  nodesep: 50
  ranksep: 80

For each node:
  g.setNode(id, { width: 140, height: 50, label })

For each edge:
  g.setEdge(from, to, { id })

dagre.layout(g) → positions all nodes

Render:
  <svg>
    <defs><marker for arrowheads/></defs>
    <!-- Arrows (edges) -->
    {edges.map(e => <path d={...} marker-end="url(#arrow)" />)}
    <!-- Nodes -->
    {nodes.map(n => <g transform={translate(x,y)}>
      <rect ... />
      <text>{label}</text>
    </g>)}
  </svg>
```

### Visual Design

Each node is a colored rectangle:
- **Agent nodes**: blue background, agent name + ID
- **System nodes**: gray, for service announcements

Each edge is a directed arrow:
- **Task (dispatch)**: solid blue arrow, from dispatcher to executor
- **Reply**: dashed green arrow, from executor back to dispatcher

Edge tooltip shows: summary, timestamp, reply content.

### Interaction

- **Hover edge** → highlight the full task flow (both task and reply edges)
- **Click edge** → side panel shows the complete conversation for that task
- **Auto-refresh** → polling every 5s for new events

### Layout Structure

```
┌─ Collaboration Page ─────────────────────────────────┐
│ [Graph] ← full screen, DAG in center                  │
│                                                       │
│   leader                                              │
│     │ (task)                                          │
│     ▼                                                 │
│   employee_a                                          │
│     │ (reply, dashed)                                 │
│     ▼                                                 │
│   leader                                              │
│                                                       │
│ ── Side Panel (on edge click) ────────────────────── │
│ │ Task #3                                            │ │
│ │ leader → employee_a                                │ │
│ │ "Dispatching task: Hello 员工A..."                  │ │
│ │                                                    │ │
│ │ Reply:                                             │ │
│ │ employee_a → leader                                │ │
│ │ "Message received by employee_a"                   │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### Route

Add to `App.tsx`:
```typescript
import Collaboration from "@/pages/Collaboration";
// ...
<Route path="/collaboration" element={<Collaboration />} />
```

Add sidebar link:
```typescript
{ to: "/collaboration", label: "协作图", icon: GitBranch },
```

### Dependencies

```json
// web-ui/package.json
"dagre": "^0.8.5"
// Type defs
"@types/dagre": "^0.7.52"
```

## Integration with Chat

- DAG edge shows **task_id** → clicking opens side panel with the full conversation
- Chat message metadata includes **task_id** when it's part of a collaboration flow
- Future: from the Chat page, a "View in Collaboration" button on messages

## Files Changed Summary

| File | Change |
|------|--------|
| `src/message_bus.rs` | Add `task_id: Option<u64>` to ChatMessage |
| `src/main.rs` | Assign `task_id` in `check_and_process_dispatches()` |
| `web/routes/collaboration.py` | NEW — `/api/collaboration/graph` and `/events` |
| `web/main.py` | Include collaboration router |
| `web-ui/package.json` | Add `dagre` + `@types/dagre` |
| `web-ui/src/pages/Collaboration.tsx` | NEW — DAG visualization page |
| `web-ui/src/App.tsx` | Add /collaboration route |
| `web-ui/src/components/Sidebar.tsx` | Add "协作图" nav link |
