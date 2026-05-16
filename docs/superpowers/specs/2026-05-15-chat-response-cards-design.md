# Chat Response Card Architecture

Date: 2026-05-15
Status: approved, in-progress

## Overview

Every AI response in chat becomes a **self-contained unit** with:

```
┌─────────────────────────────────────┐
│ 🧠 思考过程            [auto-fold]  │  ← thinking card (R1/V4 models only)
├─────────────────────────────────────┤
│ 🔧 工具调用记录         [auto-fold]  │  ← tool cards
│  ├ 读取文件    ✓ 0.02s              │
│  ├ 编辑文件    ✓ 0.01s              │
│  └ 执行命令    ⏳ 0.3s...           │
├─────────────────────────────────────┤
│ 📊 DAG 任务流程        [auto-fold]  │  ← DAG SVG (only when define_dag called)
├─────────────────────────────────────┤
│ [AI 回复正文 — Markdown]            │
└─────────────────────────────────────┘
```

Three sub-features: persistence, tool name localization, reasoning card.

---

## 1. Persistence (survives refresh)

### Current state
- `toolCalls` lives in React `useState` — lost on refresh
- `turnDagRuns` also useState — lost on refresh  
- `streamRef` is useRef — lost on refresh
- Sessions are already persisted in localStorage

### Design

Extend the `Message` interface to carry optional metadata:

```typescript
interface Message {
  id: string
  role: "user" | "assistant"
  content: string

  // New metadata fields (optional, only on assistant messages)
  tools?: ToolCallRecord[]          // tool calls made in this turn
  dagRunIds?: string[]              // DAG run_ids created in this turn  
  reasoningText?: string            // thinking/reasoning content (R1 models)
}
```

**Save flow:**
1. Tool call events accumulate → `toolCalls` state (real-time display)
2. When `setStreaming(false)`, serialize `toolCalls` into the Message metadata
3. Call `updateMessages()` with the enriched message

**Load flow:**
1. Session loads from localStorage with tool/dag metadata intact
2. When viewing a historical message, render its tool cards from `m.tools`
3. DAG runs are fetched from `/api/dag/{run_id}` on-demand (since dag.yaml may still exist on disk)

**For DAG:** Store `dagRunIds` in the message metadata. On load, fetch each run from the API and render with DagGraph. Completed DAGs are read-only (no polling, no auto-expand).

---

## 2. Tool Name Localization

### Current state
Tool names are raw function identifiers: `read_file`, `write_file`, `bash`, `define_dag`, etc.

### Design

Add a localization map in `/web-ui/src/lib/tool-names.ts`:

```typescript
export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  read_file:     "读取文件",
  write_file:    "写入文件",
  edit_file:     "编辑文件",
  list_dir:      "浏览目录",
  bash:          "执行命令",
  glob:          "文件搜索",
  grep:          "内容搜索",
  web_search:    "网页搜索",
  web_fetch:     "获取网页",
  browser:       "浏览器操作",
  define_dag:    "定义任务",
  append_stage:  "追加阶段",
  update_dag:    "更新任务",
  dispatch_task: "派发任务",
  check_tasks:   "检查进度",
  stop_task:     "停止任务",
  todo_write:    "任务清单",
  recall:        "记忆搜索",
  pin:           "固定事实",
  unpin:         "取消固定",
  record_experience: "记录经验",
  recall_experience: "回顾经验",
  cron:          "定时任务",
  current_status: "状态检查",
  wait:          "等待",
  sub_agent:     "子代理",
}
```

All UI that displays tool names uses `TOOL_DISPLAY_NAMES[name] || name`.

---

## 3. Reasoning/Thinking Card

### Current state
`reasoningText` is shown as a small muted bubble during streaming only. Lost after streaming ends.

### Design

1. During streaming: show inline (existing behavior, keep it)
2. After streaming ends: embed `reasoningText` into the Message metadata as `message.reasoningText`
3. When rendering historical messages: if `m.reasoningText` exists, show a collapsible card above the reply

**Card appearance:**
```
┌────────────────────────────────────────┐
│ 🧠 思考过程                    [展开 ▼] │
│ ┌────────────────────────────────────┐ │
│ │ 嗯，用户想要...                      │ │  ← collapsible, muted styling
│ │ 我应该先分析...                      │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

Same `auto-collapse after streaming` rule: when the response completes, collapsed. User can manually expand.

---

## Implementation Plan

### Step 1: Extend Message interface + persistence
- `Chat.tsx`: add optional fields to `Message`
- `Chat.tsx`: on streaming end, save `tools`, `dagRunIds`, `reasoningText` into the assistant message
- `Chat.tsx`: render historical tools/dag from message metadata

### Step 2: Tool name localization  
- Create `web-ui/src/lib/tool-names.ts`
- Import and use in Chat.tsx tool card rendering

### Step 3: Reasoning/thinking card
- `Chat.tsx`: embed `reasoningText` into message on completion
- `Chat.tsx`: render reasoning card above reply for historical messages

### Step 4: Review DAG positioning
- `Chat.tsx`: order of cards — Thinking → Tools → DAG (SVG) → Reply text
- Each card independently collapsible via click on header
