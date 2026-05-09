# Collaboration DAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a task flow DAG visualization showing how agents collaborate — who dispatches tasks to whom, and the complete task lifecycle.

**Architecture:** Add `task_id` to Rust ChatMessage → API reads `chat/group.jsonl` → dagre layouts the DAG → SVG renders it in the browser.

**Tech Stack:** Rust (message_bus, serde), Python FastAPI, React/TypeScript, dagre

---

### Task 1: Add task_id to ChatMessage

**Files:**
- Modify: `src/message_bus.rs`
- Modify: `src/main.rs`

- [ ] **Step 1: Add `task_id` field to ChatMessage**

In `src/message_bus.rs`, add to the struct:

```rust
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub msg_id: String,
    pub task_id: Option<u64>,
    pub timestamp: String,
    pub from: String,
    pub to: String,
    pub content: String,
    pub message_type: String,
}
```

- [ ] **Step 2: Update `new_message()` to include task_id=None**

```rust
pub fn new_message(from: String, to: String, content: String, message_type: String) -> ChatMessage {
    let counter = MSG_COUNTER.fetch_add(1, Ordering::Relaxed);
    ChatMessage {
        msg_id: format!("msg_{:06}", counter),
        task_id: None,
        timestamp: chrono::Utc::now().to_rfc3339(),
        from,
        to,
        content,
        message_type,
    }
}
```

- [ ] **Step 3: Assign task_id in dispatch flow**

In `src/main.rs`, modify `check_and_process_dispatches()`. Add at the top of the function:

```rust
use std::sync::atomic::{AtomicU64, Ordering};
static NEXT_TASK_ID: AtomicU64 = AtomicU64::new(1);
```

In the dispatch loop, after the `target_id.is_empty()` check (~line 430), assign task_id and include it in log messages:

```rust
        let task_id = NEXT_TASK_ID.fetch_add(1, Ordering::Relaxed);

        message_bus::log_message(&message_bus::ChatMessage {
            task_id: Some(task_id),
            ..message_bus::new_message(
                "leader".to_string(),
                target_id.clone(),
                format!("Dispatching task: {:.80}", prompt),
                "task".to_string(),
            )
        }).ok();
```

And for the reply:

```rust
        message_bus::log_message(&message_bus::ChatMessage {
            task_id: Some(task_id),
            ..message_bus::new_message(
                target_id.clone(),
                "leader".to_string(),
                content.to_string(),
                "reply".to_string(),
            )
        }).ok();
```

And in the error case:

```rust
        message_bus::log_message(&message_bus::ChatMessage {
            task_id: Some(task_id),
            ..message_bus::new_message(
                "system".to_string(),
                "leader".to_string(),
                format!("Dispatch to {} failed: {}", target_id, e),
                "system".to_string(),
            )
        }).ok();
```

- [ ] **Step 4: Compile**

```bash
cd src && cargo build 2>&1
```

Expected: Compiles without errors.

- [ ] **Step 5: Commit**

```bash
git add src/message_bus.rs src/main.rs
git commit -m "feat(collaboration): add task_id to ChatMessage for dispatch-reply pairing"
```

---

### Task 2: Create collaboration API

**Files:**
- Create: `web/routes/collaboration.py`
- Modify: `web/main.py`

- [ ] **Step 1: Create `web/routes/collaboration.py`**

```python
"""Collaboration graph API — reads Rust message bus data and returns DAG structure."""
import json
from pathlib import Path
from fastapi import APIRouter, Request

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent


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

    # Build unique agent nodes
    agent_ids = set()
    for m in messages:
        f = m.get("from", "")
        t = m.get("to", "")
        if f and f != "system":
            agent_ids.add(f)
        if t and t not in ("*", "system", ""):
            agent_ids.add(t)

    # Load agent names from config.toml
    import tomllib
    config_path = BASE_DIR / "agents" / "config.toml"
    agent_names = {}
    if config_path.exists():
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        for a in config.get("agents", []):
            agent_names[a["id"]] = a.get("name", a["id"])

    nodes = [
        {"id": aid, "label": agent_names.get(aid, aid)}
        for aid in sorted(agent_ids)
    ]

    # Group by task_id
    tasks = {}
    for m in messages:
        tid = m.get("task_id")
        if tid is None:
            continue
        if tid not in tasks:
            tasks[tid] = {"task": None, "replies": []}
        if m.get("message_type") == "task":
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
            "summary": task.get("content", "")[:100],
            "timestamp": task.get("timestamp", ""),
            "replies": [
                {"from": r.get("from", ""), "content": r.get("content", "")[:200], "timestamp": r.get("timestamp", "")}
                for r in flow["replies"]
            ],
        })

    return {"nodes": nodes, "edges": edges}


@router.get("/api/collaboration/graph/events")
async def recent_events(request: Request):
    """Return edges from the last 60 seconds."""
    chat_path = BASE_DIR / "chat" / "group.jsonl"
    if not chat_path.exists():
        return {"edges": []}

    import datetime
    cutoff = (datetime.datetime.now(datetime.timezone.utc) -
              datetime.timedelta(seconds=60)).isoformat()

    recent_edges = []
    with open(chat_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    m = json.loads(line)
                    if m.get("timestamp", "") >= cutoff and m.get("message_type") in ("task", "reply"):
                        recent_edges.append(m)
                except json.JSONDecodeError:
                    pass

    return {"edges": recent_edges[-20:]}
```

- [ ] **Step 2: Register router in `web/main.py`**

Add at the bottom with other router includes:

```python
from web.routes.collaboration import router as collaboration_router
app.include_router(collaboration_router)
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/ -v --tb=short 2>&1
```

Expected: All existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add web/routes/collaboration.py web/main.py
git commit -m "feat(collaboration): add collaboration graph API endpoint"
```

---

### Task 3: Create Collaboration frontend page

**Files:**
- Create: `web-ui/src/pages/Collaboration.tsx`
- Modify: `web-ui/src/App.tsx`
- Modify: `web-ui/src/components/Sidebar.tsx`
- Modify: `web-ui/package.json`

- [ ] **Step 1: Install dagre dependency**

```bash
cd web-ui && npm install dagre @types/dagre 2>&1
```

- [ ] **Step 2: Create `web-ui/src/pages/Collaboration.tsx`**

```typescript
import { useState, useEffect, useRef, useCallback } from "react";
import dagre from "dagre";

interface GraphNode {
  id: string;
  label: string;
}

interface ReplyInfo {
  from: string;
  content: string;
  timestamp: string;
}

interface GraphEdge {
  id: string;
  from: string;
  to: string;
  task_id: number;
  type: string;
  summary: string;
  timestamp: string;
  replies: ReplyInfo[];
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface DagreNode {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface DagreEdge {
  points: { x: number; y: number }[];
}

export default function Collaboration() {
  const [data, setData] = useState<GraphData | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const resp = await fetch("/api/collaboration/graph");
        const json: GraphData = await resp.json();
        setData(json);
      } catch { /* ignore */ }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!data) {
    return <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>;
  }

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 50, ranksep: 80, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));

  data.nodes.forEach((n) => g.setNode(n.id, { width: 140, height: 50, label: n.label }));
  data.edges.forEach((e) => g.setEdge(e.from, e.to, { id: e.id }));

  dagre.layout(g);

  const nodePositions: Record<string, DagreNode> = {};
  g.nodes().forEach((id: string) => {
    const node = g.node(id);
    nodePositions[id] = { x: node.x - 70, y: node.y - 25, width: 140, height: 50 };
  });

  const edgePaths: Record<string, DagreEdge> = {};
  g.edges().forEach((e: { v: string; w: string }) => {
    const edge = g.edge(e);
    edgePaths[`${e.v}->${e.w}`] = { points: edge.points };
  });

  const svgWidth = Math.max(800, (Object.values(nodePositions).reduce((m, n) => Math.max(m, n.x + n.width + 40), 0)));
  const svgHeight = Math.max(400, (Object.values(nodePositions).reduce((m, n) => Math.max(m, n.y + n.height + 40), 0)));

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-auto p-4">
        <h1 className="text-lg font-semibold mb-4">Collaboration Graph</h1>
        <svg ref={svgRef} width={svgWidth} height={svgHeight} className="border rounded bg-white">
          <defs>
            <marker id="arrow-task" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 Z" fill="#3b82f6" />
            </marker>
            <marker id="arrow-reply" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 Z" fill="#22c55e" />
            </marker>
          </defs>

          {/* Edges */}
          {data.edges.map((edge) => {
            const ep = edgePaths[`${edge.from}->${edge.to}`];
            if (!ep) return null;
            const isTask = edge.type === "task";
            const mid = ep.points[Math.floor(ep.points.length / 2)];
            const d = ep.points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
            return (
              <g key={edge.id}>
                <path
                  d={d}
                  fill="none"
                  stroke={isTask ? "#3b82f6" : "#22c55e"}
                  strokeWidth={2}
                  strokeDasharray={isTask ? "" : "6,3"}
                  markerEnd={`url(#arrow-${isTask ? "task" : "reply"})`}
                  className="cursor-pointer hover:stroke-3 opacity-70 hover:opacity-100"
                  onClick={() => setSelectedEdge(edge)}
                />
                {mid && (
                  <text x={mid.x} y={mid.y - 8} textAnchor="middle" fontSize={10} fill="#6b7280"
                        className="pointer-events-none select-none">
                    {edge.summary.substring(0, 20)}
                  </text>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {data.nodes.map((node) => {
            const pos = nodePositions[node.id];
            if (!pos) return null;
            return (
              <g key={node.id} className="cursor-default">
                <rect x={pos.x} y={pos.y} width={pos.width} height={pos.height}
                      rx={8} ry={8} fill="#eff6ff" stroke="#3b82f6" strokeWidth={2} />
                <text x={pos.x + 70} y={pos.y + 20} textAnchor="middle" fontSize={13}
                      fontWeight="bold" fill="#1e40af">
                  {node.label}
                </text>
                <text x={pos.x + 70} y={pos.y + 36} textAnchor="middle" fontSize={10}
                      fill="#6b7280">
                  {node.id}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Side panel */}
      {selectedEdge && (
        <div className="w-80 border-l bg-gray-50 p-4 overflow-y-auto">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold">Task #{selectedEdge.task_id}</h2>
            <button onClick={() => setSelectedEdge(null)} className="text-gray-400 hover:text-gray-600">✕</button>
          </div>
          <div className="space-y-3">
            <div className="bg-white rounded p-3 border-l-4 border-blue-500">
              <div className="text-xs text-gray-500 mb-1">
                {selectedEdge.from} → {selectedEdge.to}  (task)
              </div>
              <div className="text-sm">{selectedEdge.summary}</div>
              <div className="text-xs text-gray-400 mt-1">{selectedEdge.timestamp}</div>
            </div>
            {selectedEdge.replies.map((r, i) => (
              <div key={i} className="bg-white rounded p-3 border-l-4 border-green-500">
                <div className="text-xs text-gray-500 mb-1">
                  {r.from} → {selectedEdge.from}  (reply)
                </div>
                <div className="text-sm">{r.content}</div>
                <div className="text-xs text-gray-400 mt-1">{r.timestamp}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add route to `web-ui/src/App.tsx`**

```typescript
import Collaboration from "@/pages/Collaboration"
// In the Routes, add:
<Route path="/collaboration" element={<Collaboration />} />
```

- [ ] **Step 4: Add sidebar link to `web-ui/src/components/Sidebar.tsx`**

In the `navItems` array, add:

```typescript
import { GitBranch } from "lucide-react"
// In navItems:
{ to: "/collaboration", label: "协作图", icon: GitBranch },
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd web-ui && npx tsc --noEmit 2>&1
```

Expected: No errors.

- [ ] **Step 6: Run all tests**

```bash
cd / && pytest tests/ -v --tb=short 2>&1
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add web-ui/src/pages/Collaboration.tsx web-ui/src/App.tsx web-ui/src/components/Sidebar.tsx web-ui/package.json
git commit -m "feat(collaboration): add DAG visualization page with dagre layout"
```

---

### Task 4: Integration Test

- [ ] **Step 1: Verify Rust build**

```bash
cd src && cargo build 2>&1
```

Expected: Compiles without errors.

- [ ] **Step 2: Verify Python tests**

```bash
cd / && pytest tests/ -v --tb=short 2>&1
```

Expected: All tests pass.

- [ ] **Step 3: Verify TypeScript**

```bash
cd web-ui && npx tsc --noEmit 2>&1
```

Expected: No type errors.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: finalize collaboration DAG integration"
```
