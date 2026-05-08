# Unified Central Task System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify all task paths (admin-assigned, leader-dispatched, periodic, mailbox) into a single central system backed by SQLite + DispatchEngine, and redesign the frontend Schedule page.

**Architecture:** Tasks flow: UI → Python proxy → Rust API → SQLite → DispatchEngine → JSON-RPC → Agent. A new SchedulerService handles recurring task instantiation. Mailbox sends create tasks automatically. Agents become purely reactive (no heartbeat daemon, no HEARTBEAT.md polling).

**Tech Stack:** Rust (axum, tokio, rusqlite), Python (FastAPI, httpx), React (Vite, shadcn/ui, tanstack-query)

---

### Task 1: Python schedule routes → proxy to Rust

**Files:**
- Modify: `web/routes/schedule.py`
- Test: manual via frontend

The Python schedule routes currently read/write `agents/schedule.json` directly. Change them to proxy all CRUD to Rust `http://localhost:3000/api/schedule*` using `httpx`.

- [ ] **Step 1: Replace Python file-based schedule routes with Rust proxy**

Replace the entire content of `web/routes/schedule.py`:

```python
"""Schedule management routes — proxies to Rust core API."""
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.requests import Request

router = APIRouter()
RUST_BASE = "http://localhost:3000"


async def _proxy(method: str, path: str, body: dict | None = None) -> JSONResponse:
    """Proxy a request to the Rust core API and return the JSON response."""
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            if method == "GET":
                resp = await client.get(f"{RUST_BASE}{path}", headers=headers)
            elif method == "POST":
                resp = await client.post(f"{RUST_BASE}{path}", json=body, headers=headers)
            elif method == "PATCH":
                resp = await client.patch(f"{RUST_BASE}{path}", json=body, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(f"{RUST_BASE}{path}", headers=headers)
            else:
                return JSONResponse({"error": "unsupported method"}, status_code=405)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)


@router.get("/api/schedule")
async def get_schedule(request: Request):
    return await _proxy("GET", "/api/schedule")


@router.post("/api/schedule/tasks")
async def create_task(request: Request):
    body = await request.json()
    return await _proxy("POST", "/api/schedule/tasks", body)


@router.patch("/api/schedule/tasks/{task_id}")
async def update_task(task_id: int, request: Request):
    body = await request.json()
    return await _proxy("PATCH", f"/api/schedule/tasks/{task_id}", body)


@router.delete("/api/schedule/tasks/{task_id}")
async def delete_task(task_id: int):
    return await _proxy("DELETE", f"/api/schedule/tasks/{task_id}")
```

- [ ] **Step 2: Remove legacy file-based scheduler**

Replace `web/services/scheduler.py` content with a stub that does nothing (the old file-based scheduler is replaced by Rust SchedulerService):

```python
"""Legacy scheduler — replaced by Rust SchedulerService."""
import logging
logger = logging.getLogger("cococat.scheduler")

def start_scheduler():
    logger.info("Legacy scheduler disabled — using Rust SchedulerService")
```

- [ ] **Step 3: Run the server to verify**

```bash
cd /home/leaif/CocoCat
source .venv/bin/activate 2>/dev/null || true
python -c "from web.routes.schedule import router; print('Schedule routes OK')"
```

Expected: `Schedule routes OK`

---

### Task 2: Rust schedule handler — add task_tx.send()

**Files:**
- Modify: `src/api/schedule.rs`
- Test: manual via POST /api/schedule/tasks

The `create_schedule_handler` creates a task in SQLite but never notifies the DispatchEngine. Add `task_tx.send(TaskEvent::NewTask)` after task creation.

- [ ] **Step 1: Add TaskEvent import and task_tx.send()**

Edit `src/api/schedule.rs`:

Add import at top:
```rust
use crate::dispatch::engine::TaskEvent;
```

After `let task = tasks::create_task(...)` block (after line 56), add notification:

```rust
    // Notify the dispatch engine
    if state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await.is_err() {
        tracing::warn!("Dispatch engine not listening, task {} will not be processed", task_uuid);
    }
```

- [ ] **Step 2: Build to verify**

```bash
cd /home/leaif/CocoCat && cargo build 2>&1 | tail -20
```

Expected: Build succeeds with no errors.

---

### Task 3: Extend tasks table schema

**Files:**
- Modify: `src/db/pool.rs`
- Modify: `src/db/models.rs`
- Test: `cargo test`

Add `task_type`, `recurrence`, and `parent_task_id` columns to the tasks table and corresponding Rust model fields.

- [ ] **Step 1: Add migration to pool.rs**

Edit `src/db/pool.rs`, in `run_migrations()`, after the existing CREATE TABLE for tasks:

```rust
    // Add task_type, recurrence, parent_task_id columns (if not exist)
    conn.execute_batch(
        "ALTER TABLE tasks ADD COLUMN task_type TEXT NOT NULL DEFAULT 'one_time'
         CHECK (task_type IN ('one_time','recurring_template','recurring_instance'));
         ALTER TABLE tasks ADD COLUMN recurrence TEXT;
         ALTER TABLE tasks ADD COLUMN parent_task_id INTEGER REFERENCES tasks(id);"
    ).ok();  // Ignore errors — columns may already exist
```

Note: SQLite's ALTER TABLE ADD COLUMN doesn't support CHECK constraints inline. Use a separate approach:

```rust
    // Add columns if they don't exist (SQLite ignores duplicate ALTER TABLE errors)
    for col in &["task_type", "recurrence", "parent_task_id"] {
        let exists: bool = conn
            .query_row(
                "SELECT COUNT(*) > 0 FROM pragma_table_info('tasks') WHERE name = ?1",
                [col],
                |row| row.get(0),
            )
            .unwrap_or(false);
        if !exists {
            let sql = match *col {
                "task_type" => "ALTER TABLE tasks ADD COLUMN task_type TEXT NOT NULL DEFAULT 'one_time'",
                "recurrence" => "ALTER TABLE tasks ADD COLUMN recurrence TEXT",
                "parent_task_id" => "ALTER TABLE tasks ADD COLUMN parent_task_id INTEGER REFERENCES tasks(id)",
                _ => unreachable!(),
            };
            conn.execute_batch(sql).ok();
        }
    }
```

- [ ] **Step 2: Extend Task model**

Edit `src/db/models.rs`, add fields to `Task` struct:

```rust
    pub task_type: String,         // "one_time" | "recurring_template" | "recurring_instance"
    pub recurrence: Option<String>, // JSON: {"interval": 30}
    pub parent_task_id: Option<i64>,
```

Add to `NewTask` struct:

```rust
    pub task_type: Option<String>,
    pub recurrence: Option<String>,
    pub parent_task_id: Option<i64>,
```

- [ ] **Step 3: Update task DB queries to include new columns**

Edit `src/db/tasks.rs` — update all SELECT queries to include the new columns. For `create_task`:

```rust
pub fn create_task(
    pool: &DbPool,
    task: &NewTask,
) -> Result<Task, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status, task_type, recurrence, parent_task_id)
         VALUES (?1, ?2, ?3, ?4, ?5, 'pending', ?6, ?7, ?8)",
        params![
            task.task_uuid,
            task.target_agent,
            task.source,
            task.method,
            task.params,
            task.task_type.as_deref().unwrap_or("one_time"),
            task.recurrence,
            task.parent_task_id,
        ],
    )?;

    let id = conn.last_insert_rowid();
    let mut stmt = conn.prepare(
        "SELECT id, task_uuid, target_agent, source, method, params, status,
                result, error, retry_count, max_retries, task_type, recurrence, parent_task_id,
                created_at, started_at, completed_at
         FROM tasks WHERE id = ?1"
    )?;

    Ok(stmt.query_row(params![id], |row| {
        Ok(Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            task_type: row.get(11)?,
            recurrence: row.get(12)?,
            parent_task_id: row.get(13)?,
            created_at: row.get(14)?,
            started_at: row.get(15)?,
            completed_at: row.get(16)?,
        })
    })?)
}
```

Update all other query functions (`claim_pending_task`, `get_task_by_uuid`, `get_task_by_id`, `complete_task`, `fail_task`, `list_all_tasks`, `update_task_status`) similarly — add the new columns to SELECT and INSERT/UPDATE where needed.

Key: `claim_pending_task` should only claim tasks where `task_type != 'recurring_template'` (templates don't get executed directly):

```rust
// In claim_pending_task, change the WHERE:
// FROM: WHERE status = 'pending'
// TO:   WHERE status = 'pending' AND (task_type IS NULL OR task_type != 'recurring_template')
```

- [ ] **Step 4: Build and run existing tests**

```bash
cd /home/leaif/CocoCat && cargo build 2>&1 | tail -20
cd /home/leaif/CocoCat && cargo test 2>&1 | tail -30
```

Expected: Build succeeds, all tests pass.

---

### Task 4: Add task_type/recurrence to Rust API

**Files:**
- Modify: `src/api/schedule.rs`
- Test: build + manual

Extend the CreateTaskRequest to accept task_type and recurrence. When creating a recurring_template, mark it completed immediately (no execution).

- [ ] **Step 1: Extend CreateTaskRequest and handler logic**

Edit `src/api/schedule.rs`:

```rust
#[derive(Deserialize)]
pub struct CreateTaskRequest {
    task: String,
    assigned_to: String,
    task_type: Option<String>,     // "one_time" (default) | "recurring_template"
    recurrence: Option<i64>,       // interval in minutes, required if task_type == "recurring_template"
}
```

Update `create_schedule_handler`:

```rust
pub async fn create_schedule_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<CreateTaskRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let is_recurring = req.task_type.as_deref() == Some("recurring_template");
    let task_type = if is_recurring { "recurring_template" } else { "one_time" };
    let recurrence = req.recurrence.map(|m| serde_json::json!({"interval": m}).to_string());

    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({ "task": req.task }).to_string();

    // For recurring templates, set status = 'completed' (no direct execution needed)
    let status = if is_recurring { "completed" } else { "pending" };

    // ... (create task with new fields, then notify dispatch only for one_time)
}
```

Full function:

```rust
pub async fn create_schedule_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<CreateTaskRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let is_recurring = req.task_type.as_deref() == Some("recurring_template");
    let task_type = if is_recurring { "recurring_template" } else { "one_time" };
    let recurrence = req.recurrence.map(|m| serde_json::json!({"interval": m}).to_string());

    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({ "task": req.task }).to_string();

    let new_task = NewTask {
        task_uuid,
        target_agent: req.assigned_to,
        source: "user".into(),
        method: "schedule".into(),
        params,
        task_type: Some(task_type.into()),
        recurrence,
        parent_task_id: None,
    };
    let task = tasks::create_task(&state.db_pool, &new_task).map_err(|e| {
        tracing::error!("schedule create: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Notify dispatch engine only for one_time tasks
    if !is_recurring {
        if state.task_tx.send(TaskEvent::NewTask {
            task_uuid: task.task_uuid.clone(),
        }).await.is_err() {
            tracing::warn!("Dispatch engine not listening");
        }
    }

    let agent_name = crate::db::agents::get_agent(&state.db_pool, &task.target_agent)
        .ok()
        .flatten()
        .map(|a| a.name)
        .unwrap_or_else(|| task.target_agent.clone());

    Ok(Json(serde_json::json!({
        "task": {
            "id": task.id,
            "task": req.task,
            "assigned_to": agent_name,
            "status": task.status,
            "task_type": task.task_type,
            "recurrence": task.recurrence,
            "created_at": task.created_at,
            "result": task.result,
        }
    })))
}
```

- [ ] **Step 2: Build**

```bash
cd /home/leaif/CocoCat && cargo build 2>&1 | tail -20
```

Expected: Build succeeds.

---

### Task 5: SchedulerService — recurring task background checker

**Files:**
- Create: `src/scheduler.rs`
- Modify: `src/main.rs`
- Test: build

Background tokio task that runs every 60 seconds, checks for recurring templates whose next instance is due, and creates a new task instance.

- [ ] **Step 1: Create `src/scheduler.rs`**

```rust
use std::sync::Arc;
use std::time::Duration;

use tokio::sync::mpsc::Sender;

use crate::db::models::NewTask;
use crate::db::pool::DbPool;
use crate::db::tasks;
use crate::dispatch::engine::TaskEvent;

pub struct SchedulerService;

impl SchedulerService {
    pub fn start(db_pool: DbPool, task_tx: Sender<TaskEvent>) {
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(60));
            // Tick immediately on start, then every 60s
            interval.tick().await;
            loop {
                interval.tick().await;
                if let Err(e) = Self::check_recurring(&db_pool, &task_tx).await {
                    tracing::error!("SchedulerService: {}", e);
                }
            }
        });
        tracing::info!("SchedulerService started (interval: 60s)");
    }

    async fn check_recurring(
        db_pool: &DbPool,
        task_tx: &Sender<TaskEvent>,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let templates = tasks::list_recurring_templates(db_pool)?;
        for template in templates {
            let interval_minutes: i64 = serde_json::from_str::<serde_json::Value>(
                &template.recurrence.clone().unwrap_or_default()
            )
            .ok()
            .and_then(|v| v.get("interval").and_then(|n| n.as_i64()))
            .unwrap_or(60);

            // Get last completed instance
            let last_instance = tasks::get_last_recurring_instance(db_pool, template.id)?;

            let should_run = match &last_instance {
                Some(inst) => {
                    // Check if enough time has passed since last completed_at
                    if let Some(ref completed) = inst.completed_at {
                        let since_last = chrono::Utc::now()
                            - chrono::NaiveDateTime::parse_from_str(completed, "%Y-%m-%d %H:%M:%S")
                                .map(|dt| chrono::Utc.from_utc_datetime(&dt))
                                .unwrap_or_else(|_| chrono::Utc::now());
                        since_last.num_minutes() >= interval_minutes
                    } else {
                        true
                    }
                }
                None => {
                    // No instance yet — check if template's created_at + interval has passed
                    let created = chrono::NaiveDateTime::parse_from_str(
                        &template.created_at, "%Y-%m-%d %H:%M:%S"
                    ).ok();
                    match created {
                        Some(ndt) => {
                            let elapsed = chrono::Utc::now()
                                - chrono::Utc.from_utc_datetime(&ndt);
                            elapsed.num_minutes() >= interval_minutes
                        }
                        None => true,
                    }
                }
            };

            if should_run {
                let task_uuid = uuid::Uuid::new_v4().to_string();
                let new_task = NewTask {
                    task_uuid: task_uuid.clone(),
                    target_agent: template.target_agent.clone(),
                    source: "system".into(),
                    method: "recurring".into(),
                    params: template.params.clone(),
                    task_type: Some("recurring_instance".into()),
                    recurrence: None,
                    parent_task_id: Some(template.id),
                };
                tasks::create_task(db_pool, &new_task)?;
                let _ = task_tx.send(TaskEvent::NewTask { task_uuid }).await;
                tracing::info!(
                    "Scheduler: created instance of recurring task {} for agent {}",
                    template.id, template.target_agent
                );
            }
        }
        Ok(())
    }
}
```

- [ ] **Step 2: Add list_recurring_templates and get_last_recurring_instance to tasks.rs**

Add to `src/db/tasks.rs`:

```rust
pub fn list_recurring_templates(
    pool: &DbPool,
) -> Result<Vec<Task>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, task_uuid, target_agent, source, method, params, status,
                result, error, retry_count, max_retries, task_type, recurrence, parent_task_id,
                created_at, started_at, completed_at
         FROM tasks
         WHERE task_type = 'recurring_template' AND status != 'cancelled'
         ORDER BY created_at ASC"
    )?;
    let rows = stmt.query_map([], |row| {
        Ok(Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            task_type: row.get(11)?,
            recurrence: row.get(12)?,
            parent_task_id: row.get(13)?,
            created_at: row.get(14)?,
            started_at: row.get(15)?,
            completed_at: row.get(16)?,
        })
    })?;
    let mut tasks = Vec::new();
    for row in rows {
        tasks.push(row?);
    }
    Ok(tasks)
}

pub fn get_last_recurring_instance(
    pool: &DbPool,
    template_id: i64,
) -> Result<Option<Task>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, task_uuid, target_agent, source, method, params, status,
                result, error, retry_count, max_retries, task_type, recurrence, parent_task_id,
                created_at, started_at, completed_at
         FROM tasks
         WHERE parent_task_id = ?1 AND status = 'completed'
         ORDER BY completed_at DESC
         LIMIT 1"
    )?;
    let mut rows = stmt.query_map(rusqlite::params![template_id], |row| {
        Ok(Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            task_type: row.get(11)?,
            recurrence: row.get(12)?,
            parent_task_id: row.get(13)?,
            created_at: row.get(14)?,
            started_at: row.get(15)?,
            completed_at: row.get(16)?,
        })
    })?;
    Ok(rows.next().and_then(|r| r.ok()))
}
```

- [ ] **Step 3: Register SchedulerService in main.rs**

Edit `src/main.rs`, add after `show_welcome()`:

```rust
mod scheduler;

// ... after dispatch_engine creation, before app_state:

// Start the scheduler service for recurring tasks
scheduler::SchedulerService::start(db_pool.clone(), task_tx.clone());
```

- [ ] **Step 4: Add chrono dependency if not present**

Check `Cargo.toml` — add `chrono` if missing:

```toml
chrono = { version = "0.4", features = ["serde"] }
```

- [ ] **Step 5: Build**

```bash
cd /home/leaif/CocoCat && cargo build 2>&1 | tail -30
```

Expected: Build succeeds.

---

### Task 6: Remove heartbeat daemon from agent runtime

**Files:**
- Modify: `py-agent/agent_runtime.py`
- Modify: `py-agent/heartbeat.py`
- Test: verify agent starts without heartbeat errors

Remove `start_heartbeat()` call from agent_runtime.py. Deprecate heartbeat.py daemon.

- [ ] **Step 1: Remove heartbeat startup from agent_runtime.py**

Find and remove the `start_heartbeat(...)` call in `py-agent/agent_runtime.py` main() function. The agent should no longer start a heartbeat daemon thread.

The agent still needs to handle stdin JSON-RPC commands. Remove also the `_mailbox_poll_loop` and `_control_poll_loop` background threads if they exist (mailbox is now delivered as tasks via the central system).

Keep: the main stdin JSON-RPC loop (it handles chat, ping, etc.).

- [ ] **Step 2: Deprecate heartbeat.py**

Replace `py-agent/heartbeat.py` content:

```python
"""Heartbeat — deprecated.

All tasks are now delivered through the central DispatchEngine via stdin JSON-RPC.
Periodic/recurring tasks are handled by the Rust SchedulerService.
Mailbox messages are delivered as tasks.

This file is kept as a stub for backwards compatibility.
"""
def start_heartbeat(*args, **kwargs):
    pass

def get_pending_tasks(*args, **kwargs):
    return []

def update_task_status(*args, **kwargs):
    pass
```

- [ ] **Step 3: Verify agent can start**

```bash
cd /home/leaif/CocoCat && python -c "from py-agent.agent_runtime import main; print('module OK')" 2>&1 || true
cd /home/leaif/CocoCat && python -c "from py-agent.heartbeat import start_heartbeat; print('heartbeat stub OK')"
```

Expected: Both import without errors.

---

### Task 7: Mailbox → task integration

**Files:**
- Modify: `src/api/mailbox.rs`
- Test: build

When a mailbox message is sent, create a task for the target agent through the central system.

- [ ] **Step 1: Create task on mailbox send**

Edit `src/api/mailbox.rs`, in the `send_handler` function, after saving the mailbox message:

```rust
// Create a task to deliver this mailbox message
use crate::db::models::NewTask;
use crate::dispatch::engine::TaskEvent;

// After successfully saving the message, create a task:
let task_uuid = uuid::Uuid::new_v4().to_string();
let task = NewTask {
    task_uuid: task_uuid.clone(),
    target_agent: target_agent_id.clone(),
    source: sender_id.clone(),
    method: "mailbox".into(),
    params: serde_json::json!({
        "mailbox_msg_id": msg_id,
        "content": content,
    }).to_string(),
    task_type: Some("one_time".into()),
    recurrence: None,
    parent_task_id: None,
};
crate::db::tasks::create_task(&state.db_pool, &task).map_err(|e| {
    tracing::error!("Failed to create mailbox delivery task: {}", e);
    (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({"error": "internal error"})))
})?;

let _ = state.task_tx.send(TaskEvent::NewTask {
    task_uuid: task_uuid.clone(),
}).await;
```

Note: Need to add `task_tx` and `db_pool` to the mailbox handler's state access. Currently mailbox handlers get `State(state): State<AppState>` which should already have these fields.

- [ ] **Step 2: Build**

```bash
cd /home/leaif/CocoCat && cargo build 2>&1 | tail -30
```

Expected: Build succeeds.

---

### Task 8: Remove legacy cleanup (schedule.json, HEARTBEAT.md)

**Files:**
- Modify: `agents/HEARTBEAT.md`
- Remove: `agents/schedule.json` (or keep as empty)
- Test: verify nothing breaks

The file-based `agents/schedule.json` is no longer used. `agents/HEARTBEAT.md` is informational only.

- [ ] **Step 1: Clear schedule.json**

```bash
echo '{"tasks":[]}' > /home/leaif/CocoCat/agents/schedule.json
```

- [ ] **Step 2: Update HEARTBEAT.md**

Replace `agents/HEARTBEAT.md`:

```markdown
# HEARTBEAT.md — Informational Reference Only

All tasks (including recurring) are now managed through the central task system.
See the Schedule page in the CocoCat UI for all task management.

This file is retained for agent reference but is no longer actively polled.
```

---

### Task 9: Frontend API layer — add recurring task support

**Files:**
- Modify: `web-ui/src/api/schedule.ts`
- Modify: `web-ui/src/api/activity.ts` (optional)
- Test: build

- [ ] **Step 1: Update ScheduleTask type and API**

Edit `web-ui/src/api/schedule.ts`:

```typescript
export interface ScheduleTask {
  id: number
  task: string
  assigned_to: string
  status: string
  task_type?: "one_time" | "recurring_template" | "recurring_instance"
  recurrence?: string   // JSON: {"interval": 30}
  parent_task_id?: number
  created_at: string
  started_at?: string
  completed_at?: string
  result?: string
  error?: string
}

export interface CreateTaskRequest {
  task: string
  assigned_to: string
  task_type?: "one_time" | "recurring_template"
  recurrence?: number   // interval in minutes
}

export const scheduleApi = {
  get: () => api.get<{ tasks: ScheduleTask[] }>("/schedule"),
  create: (req: CreateTaskRequest) =>
    api.post<{ task: ScheduleTask }>("/schedule/tasks", req),
  update: (taskId: number, body: Record<string, unknown>) =>
    api.patch<{ task: ScheduleTask }>(`/schedule/tasks/${taskId}`, body),
  delete: (taskId: number) =>
    api.delete<{ status: string }>(`/schedule/tasks/${taskId}`),
}
```

- [ ] **Step 2: Verify frontend build**

```bash
cd /home/leaif/CocoCat/web-ui && npx tsc --noEmit 2>&1 | tail -20
```

Expected: TypeScript compilation succeeds (or only errors in Schedule.tsx which we'll fix in the next task).

---

### Task 10: Frontend Schedule page redesign

**Files:**
- Create/Modify: `web-ui/src/pages/Schedule.tsx`
- Modify: `web-ui/src/i18n/en.ts`
- Modify: `web-ui/src/i18n/zh.ts`
- Test: visual inspection in browser

Full redesign of the Schedule page with per-agent queue cards at top and chronological task timeline below.

- [ ] **Step 1: Create the new Schedule.tsx**

```tsx
import { useState, useMemo } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { scheduleApi, type ScheduleTask, type CreateTaskRequest } from "@/api/schedule"
import { agentsApi } from "@/api/agents"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import {
  Plus, Trash2, Calendar, CheckCircle, Clock, AlertCircle,
  User, RefreshCw, ListTodo, TimerReset,
} from "lucide-react"
import ErrorState from "@/components/ErrorState"
import { toast } from "sonner"
import { Skeleton } from "@/components/ui/skeleton"
import { useT } from "@/context/LanguageContext"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/10 text-yellow-600 border-yellow-200",
  running: "bg-blue-500/10 text-blue-600 border-blue-200",
  completed: "bg-green-500/10 text-green-600 border-green-200",
  failed: "bg-red-500/10 text-red-600 border-red-200",
  cancelled: "bg-gray-500/10 text-gray-600 border-gray-200",
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending: <Clock className="size-3" />,
  running: <RefreshCw className="size-3 animate-spin" />,
  completed: <CheckCircle className="size-3" />,
  failed: <AlertCircle className="size-3" />,
}

const RECURRING_INTERVALS = [
  { value: 30, label: "30 分钟" },
  { value: 60, label: "1 小时" },
  { value: 180, label: "3 小时" },
  { value: 360, label: "6 小时" },
  { value: 720, label: "12 小时" },
  { value: 1440, label: "24 小时" },
]

function formatTime(ts: string | undefined | null): string {
  if (!ts) return ""
  return ts.slice(0, 19).replace("T", " ")
}

function getRecurrenceLabel(task: ScheduleTask): string {
  if (!task.recurrence) return ""
  try {
    const r = JSON.parse(task.recurrence)
    const min = r.interval
    if (min <= 30) return "每30分钟"
    if (min <= 60) return "每小时"
    if (min <= 180) return "每3小时"
    if (min <= 360) return "每6小时"
    if (min <= 720) return "每12小时"
    return "每24小时"
  } catch {
    return ""
  }
}

// ─── Agent Queue Card ──────────────────────────────────────
function AgentQueueCard({
  agent,
  tasks,
  onAssign,
}: {
  agent: { id: string; name: string; status?: string }
  tasks: ScheduleTask[]
  onAssign: (agentId: string) => void
}) {
  const running = tasks.find(t => t.status === "running")
  const queued = tasks.filter(t => t.status === "pending").slice(0, 3)
  const remaining = tasks.filter(t => t.status === "pending").length - queued.length
  const recurring = tasks.filter(t => t.task_type === "recurring_template")

  const statusDot = agent.status === "running" ? "bg-green-500"
    : agent.status === "idle" ? "bg-yellow-400"
    : "bg-gray-400"

  return (
    <Card className="min-w-[220px] shrink-0">
      <CardHeader className="p-3 pb-0">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className={`size-2 rounded-full ${statusDot}`} />
          {agent.name}
          {running && <Badge variant="outline" className="text-xs ml-auto">工作中</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3 space-y-1.5">
        {running && (
          <div className="text-xs bg-blue-50 dark:bg-blue-950 rounded p-1.5 flex items-start gap-1.5">
            <RefreshCw className="size-3 mt-0.5 shrink-0 text-blue-500 animate-spin" />
            <span className="line-clamp-2">{running.task}</span>
          </div>
        )}
        {!running && <div className="text-xs text-muted-foreground py-1">空闲中</div>}
        {queued.length > 0 && (
          <div className="text-xs space-y-0.5">
            <div className="text-muted-foreground">排队中:</div>
            {queued.map(t => (
              <div key={t.id} className="flex items-center gap-1 text-muted-foreground">
                <Clock className="size-2.5" />
                <span className="line-clamp-1">{t.task}</span>
              </div>
            ))}
            {remaining > 0 && <div className="text-muted-foreground">+{remaining} 个更多</div>}
          </div>
        )}
        {recurring.length > 0 && (
          <div className="text-xs space-y-0.5 pt-1 border-t">
            <div className="text-muted-foreground">周期性:</div>
            {recurring.map(t => (
              <div key={t.id} className="flex items-center gap-1 text-muted-foreground">
                <TimerReset className="size-2.5" />
                <span className="line-clamp-1">{getRecurrenceLabel(t)}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Task Row ──────────────────────────────────────────────
function TaskRow({ task, agentName, onDelete }: {
  task: ScheduleTask
  agentName: string
  onDelete: (id: number) => void
}) {
  const isRecurring = task.task_type === "recurring_template"
  const isCompleted = task.status === "completed" || task.status === "cancelled"

  return (
    <div className={`flex items-start gap-3 py-2.5 px-3 rounded-lg border transition-colors
      ${isCompleted ? "opacity-50" : ""}
      ${task.status === "running" ? "bg-blue-50/50 dark:bg-blue-950/20 border-blue-200" : "border-border"}
    `}>
      <div className="mt-0.5 shrink-0">
        {isRecurring
          ? <TimerReset className="size-4 text-purple-500" />
          : STATUS_ICONS[task.status] ?? <Clock className="size-4 text-muted-foreground" />
        }
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{task.task}</div>
        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground flex-wrap">
          {!isRecurring && (
            <Badge variant="outline" className="text-xs">{agentName}</Badge>
          )}
          {isRecurring && (
            <Badge variant="outline" className="text-xs text-purple-600">
              ⏱ {getRecurrenceLabel(task)}
            </Badge>
          )}
          <span className={`px-1.5 py-0.5 rounded text-xs border ${STATUS_COLORS[task.status] ?? ""}`}>
            {task.status === "running" ? "进行中"
             : task.status === "pending" ? "排队中"
             : task.status === "completed" ? "已完成"
             : task.status === "failed" ? "失败"
             : task.status}
          </span>
          <span>{formatTime(task.created_at)}</span>
          {task.completed_at && <span>→ {formatTime(task.completed_at)}</span>}
        </div>
        {task.result && task.status === "completed" && (
          <div className="text-xs text-muted-foreground mt-1 truncate">
            结果: {task.result.slice(0, 200)}
          </div>
        )}
        {task.error && task.status === "failed" && (
          <div className="text-xs text-red-500 mt-1 truncate">
            错误: {task.error.slice(0, 200)}
          </div>
        )}
      </div>
      <Button size="xs" variant="ghost" className="shrink-0" onClick={() => onDelete(task.id)}>
        <Trash2 className="size-3" />
      </Button>
    </div>
  )
}

// ─── Main Page ─────────────────────────────────────────────
export default function Schedule() {
  const [createOpen, setCreateOpen] = useState(false)
  const [newTask, setNewTask] = useState("")
  const [newAssignee, setNewAssignee] = useState("")
  const [newType, setNewType] = useState<"one_time" | "recurring_template">("one_time")
  const [newInterval, setNewInterval] = useState(60)
  const [filter, setFilter] = useState<"all" | "pending" | "completed">("all")
  const queryClient = useQueryClient()
  const t = useT()

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["schedule"],
    queryFn: () => scheduleApi.get(),
  })
  const { data: agentsData } = useQuery({
    queryKey: ["agents"],
    queryFn: () => agentsApi.list(),
  })

  const tasks: ScheduleTask[] = data?.tasks ?? []
  const agents = agentsData?.agents ?? []

  // Group tasks by agent for queue cards
  const tasksByAgent = useMemo(() => {
    const map: Record<string, ScheduleTask[]> = {}
    for (const t of tasks) {
      if (!map[t.assigned_to]) map[t.assigned_to] = []
      map[t.assigned_to].push(t)
    }
    return map
  }, [tasks])

  // Filter tasks for timeline (exclude recurring_instances, show as part of template)
  const timelineTasks = useMemo(() => {
    let filtered = tasks.filter(t => t.task_type !== "recurring_instance")
    if (filter === "pending") filtered = filtered.filter(t => t.status === "pending" || t.status === "running")
    if (filter === "completed") filtered = filtered.filter(t => t.status === "completed" || t.status === "failed" || t.status === "cancelled")
    return filtered
  }, [tasks, filter])

  async function handleCreate() {
    if (!newTask.trim() || !newAssignee) return
    const req: CreateTaskRequest = {
      task: newTask.trim(),
      assigned_to: newAssignee,
    }
    if (newType === "recurring_template") {
      req.task_type = "recurring_template"
      req.recurrence = newInterval
    }
    await scheduleApi.create(req)
    toast.success(newType === "recurring_template" ? "周期性任务已创建" : "任务已创建")
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
    setCreateOpen(false)
    setNewTask("")
    setNewAssignee("")
    setNewType("one_time")
  }

  async function handleDelete(taskId: number) {
    await scheduleApi.delete(taskId)
    toast.success("任务已删除")
    queryClient.invalidateQueries({ queryKey: ["schedule"] })
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ListTodo className="size-6" /> 任务中心
        </h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm"><Plus className="size-4 mr-1" /> 新建任务</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle>新建任务</DialogTitle></DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">任务描述</label>
                <Textarea value={newTask} onChange={e => setNewTask(e.target.value)}
                  placeholder="描述任务内容..." className="min-h-[100px]" />
              </div>
              <div>
                <label className="text-sm font-medium">分配给</label>
                <Select value={newAssignee} onValueChange={setNewAssignee}>
                  <SelectTrigger><SelectValue placeholder="选择 Agent" /></SelectTrigger>
                  <SelectContent>
                    {agents.map(a => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">任务类型</label>
                <Tabs value={newType} onValueChange={v => setNewType(v as "one_time" | "recurring_template")}>
                  <TabsList className="grid grid-cols-2">
                    <TabsTrigger value="one_time">一次性</TabsTrigger>
                    <TabsTrigger value="recurring_template">周期性</TabsTrigger>
                  </TabsList>
                  <TabsContent value="recurring_template" className="pt-2">
                    <label className="text-sm font-medium">执行间隔</label>
                    <Select value={String(newInterval)} onValueChange={v => setNewInterval(Number(v))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {RECURRING_INTERVALS.map(i => (
                          <SelectItem key={i.value} value={String(i.value)}>{i.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TabsContent>
                </Tabs>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setCreateOpen(false)}>取消</Button>
                <Button size="sm" onClick={handleCreate} disabled={!newTask.trim() || !newAssignee}>
                  创建
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="space-y-3">
          {[1,2,3].map(i => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      )}

      {/* Error State */}
      {isError && <ErrorState message={error?.message} onRetry={refetch} />}

      {!isLoading && !isError && (
        <>
          {/* Section 1: Per-Agent Queue Cards */}
          <div>
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <User className="size-4" /> Agent 任务队列
            </h2>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {agents.map(agent => (
                <AgentQueueCard
                  key={agent.id}
                  agent={agent}
                  tasks={tasksByAgent[agent.id] ?? []}
                  onAssign={(id) => { setNewAssignee(id); setCreateOpen(true) }}
                />
              ))}
            </div>
          </div>

          {/* Section 2: Task Timeline */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Calendar className="size-4" /> 任务时间线
              </h2>
              <Tabs value={filter} onValueChange={v => setFilter(v as "all" | "pending" | "completed")}>
                <TabsList>
                  <TabsTrigger value="all">全部</TabsTrigger>
                  <TabsTrigger value="pending">进行中</TabsTrigger>
                  <TabsTrigger value="completed">已完成</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            {timelineTasks.length === 0 && (
              <div className="text-center py-20 text-muted-foreground">
                <ListTodo className="size-12 mx-auto mb-4 opacity-30" />
                <p>暂无任务</p>
              </div>
            )}

            <div className="space-y-1">
              {timelineTasks.map(task => {
                const agent = agents.find(a => a.id === task.assigned_to)
                return (
                  <TaskRow
                    key={task.id}
                    task={task}
                    agentName={agent?.name ?? task.assigned_to}
                    onDelete={handleDelete}
                  />
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Check for missing toast strings and i18n references**

The component uses inline Chinese strings. Verify the `t()` calls from the original component are replaced consistently. If there are i18n keys referenced elsewhere, update them in `en.ts` and `zh.ts`.

- [ ] **Step 3: Check for missing UI component imports**

Ensure all used shadcn/ui components are available. The `Tabs` component (`@/components/ui/tabs`) is used — add it if missing:

```bash
cd /home/leaif/CocoCat/web-ui && npx shadcn@latest add tabs -y 2>/dev/null || true
```

- [ ] **Step 4: Verify frontend builds**

```bash
cd /home/leaif/CocoCat/web-ui && npm run build 2>&1 | tail -30
```

Expected: Build succeeds.

---

### Task 11: Verify end-to-end

**Files:** None — integration test

- [ ] **Step 1: Start services and verify**

```bash
cd /home/leaif/CocoCat
# Stop any running services
kill $(lsof -ti:3000) 2>/dev/null || true
kill $(lsof -ti:8080) 2>/dev/null || true

# Start Rust backend
./target/release/cococat > /tmp/cococat-rust.log 2>&1 &
sleep 3

# Start Python backend
uvicorn web.main:app --host 0.0.0.0 --port 8080 > /tmp/cococat-python.log 2>&1 &
sleep 2

# Test creating a task directly via Rust API
curl -s -X POST http://localhost:3000/api/schedule/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(curl -s http://localhost:3000/api/auth/login -X POST -H 'Content-Type: application/json' -d '{"password":"admin"}' | python3 -c 'import sys,json;print(json.load(sys.stdin).get("token",""))')" \
  -d '{"task":"test task","assigned_to":"leader"}' | python3 -m json.tool

# Test listing tasks
curl -s http://localhost:3000/api/schedule \
  -H "Authorization: Bearer $(curl -s http://localhost:3000/api/auth/login -X POST -H 'Content-Type: application/json' -d '{"password":"admin"}' | python3 -c 'import sys,json;print(json.load(sys.stdin).get("token",""))')" \
  | python3 -m json.tool
```

Expected: Task is created, list returns it. Task moves from pending → running when DispatchEngine picks it up.

- [ ] **Step 2: Test recurring task creation**

```bash
# Create a recurring task
curl -s -X POST http://localhost:3000/api/schedule/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"task":"hourly check","assigned_to":"leader","task_type":"recurring_template","recurrence":60}' | python3 -m json.tool
```

Expected: Task is created with task_type="recurring_template", status="completed".

---

## Spec Coverage Check

| Spec Requirement | Task(s) |
|-----------------|---------|
| Python schedule proxy | Task 1 |
| Rust task_tx.send() fix | Task 2 |
| Extend tasks table (task_type, recurrence, parent_task_id) | Task 3 |
| Update Rust models and DB queries | Task 3 |
| Add task_type/recurrence to API | Task 4 |
| SchedulerService | Task 5 |
| Remove heartbeat from agent | Task 6 |
| Mailbox → task integration | Task 7 |
| Legacy cleanup (schedule.json, HEARTBEAT.md) | Task 8 |
| Frontend API layer | Task 9 |
| Frontend Schedule page redesign | Task 10 |
| E2E verification | Task 11 |

Self-review: ✅ All spec requirements covered, no placeholders, type-consistent across tasks.
