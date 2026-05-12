# Knowledge Base Redesign

**Date:** 2026-05-06
**Goal:** Enable agents to autonomously maintain a multi-KB wiki system — upload sources via frontend, auto-process by agents using a skill, with real-time progress streaming.

---

## Architecture Overview

```
Frontend (Knowledge.tsx)                     Rust Axum (port 3000)                  Python Agent
┌─────────────────────────┐                ┌──────────────────────┐               ┌─────────────┐
│ KB List                  │                │ POST /api/knowledge/ │               │ Leader      │
│ Upload Panel            │ ── multipart ──→│   upload             │── dispatch ──→│  reads      │
│ Progress Panel (WS)     │                │ POST /api/knowledge/ │               │ skill ↓     │
│                         │                │   {kb}/process       │               │ Employee A  │
└─────────────────────────┘                │ GET /api/knowledge/  │               │ (ingests)   │
        ↕ WS stream                        │   {kb}/tasks         │               └─────────────┘
        (kb.progress /                      └──────────────────────┘
         kb.complete)                               │
                                            knowledge/{kb_name}/
                                            ├── raw/sources/
                                            ├── wiki/{entities,concepts}/
                                            ├── index.md
                                            └── log.md
```

---

## Knowledge Base Structure

```
knowledge/{kb_name}/
├── purpose.md            ← 自动生成（Agent 首次摄入后填充）
├── schema.md             ← 从 skills/public/knowledge-ingestion.md 复制
├── index.md              ← 目录（Agent 自动维护）
├── log.md                ← 操作日志（Agent 追加）
├── raw/sources/          ← 上传的原始文件（不可变）
└── wiki/
    ├── entities/{slug}.md   ← 实体页
    └── concepts/{slug}.md   ← 概念页
```

### KB 创建
- 用户上传文件时，在 KB 下拉框输入新名字即可创建
- 系统自动建目录 + 复制 schema 模板
- purpose.md 留空，Agent 处理第一批文件时自动填充
- 无需用户手动填写任何配置

---

## Upload & Process Flow

```
1. User selects file + KB (or creates new) → clicks "Upload"
2. POST /api/knowledge/upload
   → Rust saves file to knowledge/{kb}/raw/sources/{filename}
   → If new KB: create directory structure
   → Create dispatch task for Leader (method: "process_kb_source")
   → Return { status: "queued", task_uuid }
3. Frontend shows progress panel
4. Leader receives task:
   → Reads knowledge-ingestion skill
   → Dispatches to available agent
   → Agent processes source, sends WS progress events
5. Frontend receives WS events → updates progress panel in real-time
```

---

## API Endpoints (Rust Axum)

| Method | Route | Body | Returns |
|--------|-------|------|---------|
| `POST` | `/api/knowledge/upload` | multipart (file + kb_name) | `{ status, task_uuid, kb_name }` |
| `POST` | `/api/knowledge/{kb}/process` | `{ task_id }` | `{ status, task_uuid }` |
| `GET` | `/api/knowledge/{kb}/tasks` | — | `{ tasks: [...] }` |

### Upload Handler Logic
1. Parse multipart: file + kb_name
2. If kb_name doesn't exist in `knowledge/`:
   - Create `knowledge/{kb_name}/raw/sources/`
   - Create `knowledge/{kb_name}/wiki/entities/`
   - Create `knowledge/{kb_name}/wiki/concepts/`
   - Copy `skills/public/knowledge-ingestion.md` as `schema.md`
   - Create empty `index.md` and `log.md`
3. Write file to `knowledge/{kb_name}/raw/sources/{original_filename}`
4. Create task for Leader: `method="process_kb_source"`, `params={kb_name, filename}`
5. Return response with task_uuid

---

## WebSocket Progress Events

Frontend subscribes to task_uuid and displays a step-by-step progress panel.

| WS Event | Payload | Stage |
|----------|---------|-------|
| `kb.progress` | `{ task_uuid, content: "Leader 已接收任务" }` | Leader acknowledged |
| `kb.progress` | `{ task_uuid, content: "已委派给 employee_a" }` | Assignment |
| `kb.progress` | `{ task_uuid, content: "🔧 正在分析文件..." }` | Agent working |
| `kb.progress` | `{ task_uuid, content: "📝 创建页面: cococat-architecture" }` | Page creation |
| `kb.progress` | `{ task_uuid, content: "已更新 index.md" }` | Index update |
| `kb.complete` | `{ task_uuid, result: { pages_created, pages_updated, ... } }` | Done |

Uses the same WebSocket infrastructure as chat streaming (Task 1-7 of chat-perf-fix).

---

## Knowledge Ingestion Skill

**File:** `skills/public/knowledge-ingestion.md`

Loaded into any agent's system prompt when they participate in KB maintenance.

### Skill Content

```markdown
# Skill: Knowledge Ingestion

Process source files and maintain the wiki knowledge base.

## KB Directory Layout
- `raw/sources/` — uploaded source files (immutable, read-only)
- `wiki/entities/{slug}.md` — named things (people, projects, tools, agents)
- `wiki/concepts/{slug}.md` — ideas, patterns, techniques, architectures
- `index.md` — content catalog (auto-maintained)
- `log.md` — append-only operation log

## Wiki Page Format
Every page uses YAML frontmatter:
```yaml
---
type: entity | concept
title: Human-readable title
created: YYYY-MM-DD
sources: ["source-filename"]
tags: ["tag1", "tag2"]
related: ["page-slug-1", "page-slug-2"]
summary: One-line summary of the page's content
---
```

Use `[[Wikilink]]` format for cross-references.

## Ingest Workflow (when processing a source)
1. Read the source file from `raw/sources/`
2. Analyze: identify main topic, related entities, related concepts
3. Create ONE wiki page for the main topic (entity or concept)
4. Scan ALL existing wiki pages for entities/concepts mentioned in the source
5. For each related existing page:
   - Append new information if the source reveals something new
   - Update `related` frontmatter to include the new page
   - Add `[[wikilink]]` in a "See Also" section
6. Update `index.md`: add entry for new page
7. Append to `log.md`: record what was done
8. If this is the first source for a new KB, generate `purpose.md`

## Query Workflow
1. Read `index.md` first to find relevant pages
2. Drill into specific pages for details
3. Synthesize answers with [[wikilink]] citations

## New KB Setup
When first creating a KB:
1. Directory structure is pre-created by the system
2. No purpose.md yet — infer it from the first batch of sources
```

---

## Frontend Changes

### Knowledge.tsx — Add upload dialog
- "Upload Knowledge" button in the KB list header
- Dialog: file input + KB dropdown (with "new KB" input)
- After upload: show progress panel with streaming WS events

### KnowledgeDetail.tsx — Minor
- Show "raw sources" section: list uploaded files
- Show task history for this KB

### LiveUpdatesContext.tsx — Add event types
- `kb.progress` → store in streamState (same mechanism as chat streaming)
- `kb.complete` → update KB data

### New: ProgressPanel component
- Receives task_uuid, subscribes to stream events
- Displays timeline of steps with status icons
- Auto-collapses when complete

---

## File Changes Summary

| File | Change |
|------|--------|
| `skills/public/knowledge-ingestion.md` | **Create** — KB ingestion skill |
| `src/api/router.rs` | **Modify** — add `POST /api/knowledge/upload`, `POST /api/knowledge/{kb}/process`, `GET /api/knowledge/{kb}/tasks` |
| `src/api/knowledge.rs` | **Create** — upload + process + task status handlers |
| `src/dispatch/engine.rs` | **Modify** — handle `kb.progress` WS events (already wired for general streaming, just needs the event type) |
| `web-ui/src/pages/Knowledge.tsx` | **Modify** — add upload dialog + progress panel |
| `web-ui/src/pages/KnowledgeDetail.tsx` | **Modify** — show raw sources + task history |
| `web-ui/src/context/LiveUpdatesContext.tsx` | **Modify** — handle `kb.progress` / `kb.complete` events |
| `web-ui/src/api/knowledge.ts` | **Modify** — add `upload()`, `process()`, `taskStatus()` methods |

---

## Scope

This spec covers:
- KB directory structure and creation
- File upload via frontend
- Agent-side ingestion via skill (no new tools)
- Real-time progress streaming via WebSocket

Does NOT include:
- Lint workflow (periodic wiki health-check — future)
- Vector/embedding search (index.md + grep is sufficient at moderate scale)
- Batch upload
- Access control / permissions
