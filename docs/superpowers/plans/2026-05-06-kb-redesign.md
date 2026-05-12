# KB Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable agents to autonomously maintain a multi-KB wiki system — upload sources via frontend, auto-process by agents using a skill, with real-time progress streaming.

**Architecture:** Frontend upload → Rust API saves file + dispatches task → Leader routes to agent with ingestion skill → agent processes file into wiki pages → progress streamed via WebSocket.

**Tech Stack:** Rust (Axum), React/TypeScript (Vite), Python (agent subprocess), Markdown files

---

## File Map

| File | Responsibility |
|------|---------------|
| `skills/public/knowledge-ingestion.md` | Agent skill — defines the ingest workflow |
| `src/api/knowledge.rs` | Rust handlers: upload, process, task status |
| `src/api/router.rs` | Register new knowledge routes |
| `web-ui/src/api/knowledge.ts` | Frontend API client for upload/process |
| `web-ui/src/pages/Knowledge.tsx` | Upload dialog + progress panel |
| `web-ui/src/context/LiveUpdatesContext.tsx` | Handle `kb.progress` / `kb.complete` WS events |

---

### Task 1: Create Knowledge Ingestion Skill

**Files:**
- Create: `skills/public/knowledge-ingestion.md`

This is the core skill that tells agents how to process sources into wiki pages.

- [ ] **Step 1: Create the skill file**

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

## Ingest Workflow
When processing a new source file from `raw/sources/`:

1. Read the source file
2. Analyze: identify main topic, related entities, related concepts
3. Create ONE wiki page for the main topic (entity or concept)
4. Scan ALL existing wiki pages for entities/concepts mentioned in the source
5. For each related existing page:
   - Append new information if the source reveals something new
   - Update `related` frontmatter to include the new page
   - Add `[[wikilink]]` in a "See Also" section
6. Update `index.md`: add entry for new page
7. Append to `log.md`: record what was done
8. If this is the first source for a new KB, generate `purpose.md` from the content

## Query Workflow
When answering questions using the wiki:
1. Read `index.md` first to find relevant pages
2. Drill into specific pages for details
3. Synthesize answers with [[wikilink]] citations
```

- [ ] **Step 2: Verify skill is loadable**

The agent system reads skills from this directory. Just check the file exists at the right path:

```bash
ls -la skills/public/knowledge-ingestion.md
```

- [ ] **Step 3: Commit**

```bash
git add skills/public/knowledge-ingestion.md
git commit -m "feat: add knowledge ingestion skill"
```

---

### Task 2: Create Rust Knowledge API Handlers

**Files:**
- Create: `src/api/knowledge.rs`
- Modify: `src/api/router.rs`

- [ ] **Step 1: Create `src/api/knowledge.rs`**

```rust
use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use serde::Deserialize;
use std::path::PathBuf;

use crate::auth;
use crate::db::tasks;
use crate::db::models::NewTask;
use crate::dispatch::engine::TaskEvent;

use super::router::AppState;

#[derive(Deserialize)]
pub struct ProcessRequest {
    pub kb_name: String,
    pub filename: String,
}

pub async fn upload_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    // In a full implementation, this would use axum::extract::Multipart
    // For now, accept JSON with filename + content
    Json(req): Json<ProcessRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let kb_path = PathBuf::from("knowledge").join(&req.kb_name);

    // Create KB directory structure if new
    if !kb_path.exists() {
        std::fs::create_dir_all(kb_path.join("raw/sources"))
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        std::fs::create_dir_all(kb_path.join("wiki/entities"))
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        std::fs::create_dir_all(kb_path.join("wiki/concepts"))
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        // Copy schema template
        let template = std::path::Path::new("skills/public/knowledge-ingestion.md");
        if template.exists() {
            let _ = std::fs::copy(template, kb_path.join("schema.md"));
        }

        // Create empty index and log
        let _ = std::fs::write(kb_path.join("index.md"), "# Index\n\n");
        let _ = std::fs::write(kb_path.join("log.md"), "# Log\n\n");
    }

    let file_path = kb_path.join("raw/sources").join(&req.filename);

    // Write file placeholder (in real impl, write multipart bytes)
    std::fs::write(&file_path, &req.filename)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Create task for Leader
    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "kb_name": req.kb_name,
        "filename": req.filename,
        "source_path": file_path.to_string_lossy().to_string(),
    });

    tasks::create_task(
        &state.db_pool,
        &NewTask {
            task_uuid: task_uuid.clone(),
            target_agent: "leader".into(),
            source: "kb".into(),
            method: "process_kb_source".into(),
            params: params.to_string(),
        },
    ).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await;

    Ok(Json(serde_json::json!({
        "status": "queued",
        "task_uuid": task_uuid,
        "kb_name": req.kb_name,
    })))
}

pub async fn process_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(kb_name): Path<String>,
    Json(req): Json<serde_json::Value>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let filename = req.get("filename")
        .and_then(|v| v.as_str())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "kb_name": kb_name,
        "filename": filename,
    });

    tasks::create_task(
        &state.db_pool,
        &NewTask {
            task_uuid: task_uuid.clone(),
            target_agent: "leader".into(),
            source: "kb".into(),
            method: "process_kb_source".into(),
            params: params.to_string(),
        },
    ).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await;

    Ok(Json(serde_json::json!({
        "status": "queued",
        "task_uuid": task_uuid,
    })))
}

pub async fn tasks_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(kb_name): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let all_tasks = tasks::list_all_tasks(&state.db_pool)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Filter tasks related to this KB
    let kb_tasks: Vec<_> = all_tasks.into_iter()
        .filter(|t| t.params.contains(&kb_name))
        .collect();

    Ok(Json(serde_json::json!({ "tasks": kb_tasks })))
}
```

- [ ] **Step 2: Register routes in `src/api/router.rs`**

Add the import:
```rust
use super::knowledge;
```

Add `pub mod knowledge;` to `src/api/mod.rs`.

Add routes after existing knowledge routes (around line 45):
```rust
        .route("/api/knowledge/upload", axum::routing::post(knowledge::upload_handler))
        .route("/api/knowledge/:kb/process", axum::routing::post(knowledge::process_handler))
        .route("/api/knowledge/:kb/tasks", axum::routing::get(knowledge::tasks_handler))
```

- [ ] **Step 3: Verify compilation**

```bash
cargo check 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add src/api/knowledge.rs src/api/mod.rs src/api/router.rs
git commit -m "feat: add knowledge upload/process/tasks API endpoints"
```

---

### Task 3: Update Frontend API Client

**Files:**
- Modify: `web-ui/src/api/knowledge.ts`

- [ ] **Step 1: Add upload and process methods**

Add to the `knowledgeApi` object:

```typescript
  upload: (kbName: string, filename: string, content: string) =>
    api.post<{ status: string; task_uuid: string; kb_name: string }>("/knowledge/upload", { kb_name: kbName, filename, content }),
  process: (kbName: string, filename: string) =>
    api.post<{ status: string; task_uuid: string }>(`/knowledge/${kbName}/process`, { filename }),
  tasks: (kbName: string) =>
    api.get<{ tasks: any[] }>(`/knowledge/${kbName}/tasks`),
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd web-ui && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/api/knowledge.ts
git commit -m "feat: add knowledge upload/process API client methods"
```

---

### Task 4: Add WebSocket Event Handling for KB Progress

**Files:**
- Modify: `web-ui/src/context/LiveUpdatesContext.tsx`

The `kb.progress` and `kb.complete` events should use the same `streamState` mechanism already built for chat streaming.

- [ ] **Step 1: Add KB event cases to LiveUpdatesContext**

In the `switch (eventType)` block, add after the chat streaming cases:

```typescript
          case "kb.progress":
          case "kb.complete":
            streamState.set(data.task_uuid, { ...data, updatedAt: Date.now() })
            streamListeners.forEach(fn => fn())
            break
```

Also add `streamState.delete(data.task_uuid)` to the cleanup on completion (same pattern as `task_completed`).

- [ ] **Step 2: Verify TypeScript**

```bash
cd web-ui && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/context/LiveUpdatesContext.tsx
git commit -m "feat: handle kb.progress and kb.complete WS events"
```

---

### Task 5: Frontend Upload Dialog + Progress Panel

**Files:**
- Modify: `web-ui/src/pages/Knowledge.tsx`

Add an upload button, dialog, and progress panel to the Knowledge page.

- [ ] **Step 1: Add state and imports**

Add to imports:
```typescript
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Upload, CheckCircle, Loader2 } from "lucide-react"
import { knowledgeApi } from "@/api/knowledge"
import { streamState, streamListeners } from "@/context/LiveUpdatesContext"
```

- [ ] **Step 2: Add state variables**

Inside `Knowledge` component, before the return:

```typescript
  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [kbInput, setKbInput] = useState("")
  const [isNewKb, setIsNewKb] = useState(false)
  const [taskUuid, setTaskUuid] = useState<string | null>(null)
  const [, forceRender] = useState(0)

  useEffect(() => {
    const handler = () => forceRender(n => n + 1)
    streamListeners.add(handler)
    return () => streamListeners.delete(handler)
  }, [])

  const taskProgress = taskUuid ? streamState.get(taskUuid) : null
```

- [ ] **Step 3: Add upload handler**

```typescript
  async function handleUpload() {
    if (!selectedFile || !kbInput.trim()) return
    const res = await knowledgeApi.upload(kbInput.trim(), selectedFile.name, "placeholder content")
    setTaskUuid(res.task_uuid)
  }
```

- [ ] **Step 4: Add upload dialog JSX**

Add before the closing `</div>` of the page:

```tsx
      {/* Upload Dialog */}
      <Button onClick={() => setUploadOpen(true)} className="mb-4">
        <Upload className="size-4 mr-2" /> Upload Knowledge
      </Button>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Upload Knowledge</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">File</label>
              <Input type="file" onChange={e => setSelectedFile(e.target.files?.[0] ?? null)} />
            </div>
            <div>
              <label className="text-sm font-medium">Knowledge Base</label>
              <Input
                placeholder="Select existing or type new name..."
                value={kbInput}
                onChange={e => setKbInput(e.target.value)}
                list="kb-list"
              />
              <datalist id="kb-list">
                {data?.kbs?.map((kb: any) => (
                  <option key={kb.id} value={kb.id} />
                ))}
              </datalist>
            </div>
            <Button onClick={handleUpload} disabled={!selectedFile || !kbInput.trim()}>
              Upload & Process
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Progress Panel */}
      {taskProgress && (
        <div className="border rounded-lg p-4 mb-4 bg-muted/30">
          <h3 className="font-semibold mb-2">Processing: {taskProgress.task_uuid?.slice(0, 8)}</h3>
          <div className="space-y-1 text-sm">
            {taskProgress.event === "kb.progress" && (
              <div className="flex items-center gap-2">
                <Loader2 className="size-3 animate-spin" />
                <span>{taskProgress.content || "Processing..."}</span>
              </div>
            )}
            {taskProgress.event === "kb.complete" && (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle className="size-3" />
                <span>Complete</span>
              </div>
            )}
          </div>
        </div>
      )}
```

- [ ] **Step 5: Verify TypeScript**

```bash
cd web-ui && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 6: Commit**

```bash
git add web-ui/src/pages/Knowledge.tsx
git commit -m "feat: add upload dialog and progress panel to knowledge page"
```

---

### Task 6: Python Agent `process_kb_source` Handler

**Files:**
- Modify: `py-agent/agent_runtime.py`

The Rust dispatch engine calls the agent with `method: "process_kb_source"`. The agent needs to enter the ReAct loop so it can read the `knowledge-ingestion` skill and process the source file using `read_file`/`write_file`/`edit_file`.

- [ ] **Step 1: Add `process_kb_source` handling**

In `py-agent/agent_runtime.py`, modify the stdin loop. The current code handles `method == "chat"` with streaming; add `process_kb_source` similarly but without streaming callbacks:

```python
            if request.get("method") == "chat":
                params = request.get("params", {})
                content = params.get("content", "")
                if agent_loop is None:
                    raise RuntimeError("agent loop not initialized")
                ...
            elif request.get("method") == "process_kb_source":
                params = request.get("params", {})
                kb_name = params.get("kb_name", "")
                filename = params.get("filename", "")
                source_path = params.get("source_path", "")
                if agent_loop is None:
                    raise RuntimeError("agent loop not initialized")

                prompt = (
                    f"A new source file has been uploaded to the knowledge base '{kb_name}'. "
                    f"File: {filename}\n\n"
                    f"Read the file at {source_path}, then follow the Knowledge Ingestion skill "
                    f"to process it into wiki pages. "
                    f"Read skills/public/knowledge-ingestion.md for the exact workflow."
                )
                result = agent_loop.run(
                    prompt,
                    user_id=params.get("user_id", ""),
                    on_progress=write_progress,
                    on_tool=write_tool,
                    on_reasoning=write_reasoning,
                )
                if not isinstance(result, dict):
                    result = {"response": str(result)}
                response = {"jsonrpc": "2.0", "result": result, "id": req_id}
            else:
                result = handle_request(request, agent_loop=agent_loop)
                response = {"jsonrpc": "2.0", "result": result, "id": req_id}
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -m py_compile py-agent/agent_runtime.py
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_runtime.py
git commit -m "feat: add process_kb_source handler for knowledge ingestion"
```

---

### Task 7: End-to-End Test

**Files:** None (manual test)

- [ ] **Step 1: Restart backend**

```bash
pkill -f "target/debug/cococat" 2>/dev/null
./target/debug/cococat &
sleep 3
curl -s http://localhost:3000/api/health
```

- [ ] **Step 2: Test upload endpoint**

```bash
TOKEN=$(curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")

# Upload a test source
curl -s -X POST http://localhost:3000/api/knowledge/upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"kb_name":"test-kb","filename":"test-source.md"}' | python3 -m json.tool

# Verify KB was created
ls -la knowledge/test-kb/raw/sources/
ls -la knowledge/test-kb/wiki/entities/
ls -la knowledge/test-kb/wiki/concepts/
```

- [ ] **Step 3: Open frontend at http://localhost:5173/**

Go to Knowledge page. Click "Upload Knowledge", fill in the form, submit.
Verify progress panel appears and shows real-time updates.

- [ ] **Step 4: Clean up test KB**

```bash
rm -rf knowledge/test-kb/
```
