# Unified Central Task System — CocoCat

## Summary

Unify all task paths (admin-assigned, leader-dispatched, periodic/recurring, inter-agent mailbox) into a single central task management system backed by SQLite and dispatched through the Rust DispatchEngine. Deprecate the file-based `schedule.json` and agent-side heartbeat/HEARTBEAT.md autonomous decision loop. Agents become purely reactive: receive tasks via JSON-RPC stdin, execute, respond.

## Motivation

The current system has three independent task paths that don't coordinate:

1. **Schedule page (Python → agents/schedule.json)** — legacy file-based, not connected to DispatchEngine
2. **Chat dispatch (Rust → SQLite → DispatchEngine → JSON-RPC)** — works but only for chat
3. **HEARTBEAT.md + heartbeat daemon** — spec'd but never fully implemented; agent-side polling introduces latency and conflicts

This causes: tasks not showing in UI, tasks stuck in "pending", inconsistent state between systems, and no unified view.

## Architecture

```
UI (Schedule Page)
  │
  ├── Create one-time task
  ├── Create recurring task (with cron/interval)
  ├── View all tasks + per-agent queues
  └── Mailbox management
          │
    Python:8080 (proxy to Rust)
          │
    Rust:3000 API Server
          │
  ┌───────┴────────┐
  │                 │
  SQLite tasks      SchedulerService
  (single source    (background tokio task,
   of truth)         checks every 60s for due
                    recurring task instances)
  │                 │
  └───────┬────────┘
          │
    DispatchEngine
          │
    JSON-RPC stdin
          │
    Agent Runtime (purely reactive)
      while True:
        cmd = read_stdin()
        execute(cmd)
        write_response()
```

## Data Model

### tasks table (extended)

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_uuid TEXT UNIQUE NOT NULL,
    target_agent TEXT NOT NULL REFERENCES agents(id),
    source TEXT NOT NULL,                -- "user", "leader", "system", "mailbox"
    method TEXT NOT NULL DEFAULT 'task', -- "chat", "schedule", "mailbox", "recurring"
    params TEXT NOT NULL DEFAULT '{}',   -- JSON
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed','cancelled')),
    result TEXT,
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    task_type TEXT NOT NULL DEFAULT 'one_time'
        CHECK (task_type IN ('one_time', 'recurring_template', 'recurring_instance')),
    recurrence TEXT,                      -- JSON: null | {"interval": "30m"} | {"cron": "0 */1 * * *"}
    parent_task_id INTEGER REFERENCES tasks(id),  -- recurring_instance → recurring_template
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);
```

### Task types

| task_type | Description | recurrence field |
|-----------|-------------|------------------|
| `one_time` | Standard single task | NULL |
| `recurring_template` | Definition of a recurring task | JSON interval/cron |
| `recurring_instance` | An execution of a recurring task | NULL, parent_task_id → template |

## Components

### 1. Python Schedule Proxy

**File:** `web/routes/schedule.py`

Current: reads/writes `agents/schedule.json` directly.

Change: proxy all CRUD operations to Rust `http://localhost:3000/api/schedule*` using `httpx`, matching the pattern used by other routes (e.g., `/api/knowledge/upload`).

Routes to proxy:
- `GET /api/schedule` → `GET /api/schedule`
- `POST /api/schedule/tasks` → `POST /api/schedule/tasks`
- `PATCH /api/schedule/tasks/{id}` → `PATCH /api/schedule/tasks/{id}`
- `DELETE /api/schedule/tasks/{id}` → `DELETE /api/schedule/tasks/{id}`

### 2. Rust Schedule Handler Fix

**File:** `src/api/schedule.rs`

Current `create_schedule_handler`: creates task in SQLite but does NOT notify DispatchEngine.

Change: after `tasks::create_task()`, send `TaskEvent::NewTask { task_uuid }` via `state.task_tx`.

Also add `task_type` and `recurrence` fields to `CreateTaskRequest`:

```rust
pub struct CreateTaskRequest {
    task: String,
    assigned_to: String,
    task_type: Option<String>,     // "one_time" | "recurring_template"
    recurrence: Option<String>,   // JSON: {"interval": "30m"}
}
```

If `task_type == "recurring_template"`:
- Create task with status `completed` (no execution needed — it's the definition)
- Set `task_type = "recurring_template"`, `recurrence` field
- Do NOT send TaskEvent.NewTask (template itself doesn't need execution)

If `task_type == "one_time"` (default):
- Current behavior + send TaskEvent.NewTask

### 3. SchedulerService

**File:** `src/scheduler.rs` (new)

A background tokio task spawned in `main.rs`:

```rust
pub struct SchedulerService {
    db_pool: DbPool,
    task_tx: Sender<TaskEvent>,
}

impl SchedulerService {
    pub fn start(db_pool: DbPool, task_tx: Sender<TaskEvent>) {
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(60));
            loop {
                interval.tick().await;
                if let Err(e) = Self::check_recurring_tasks(&db_pool, &task_tx).await {
                    tracing::error!("Scheduler check failed: {}", e);
                }
            }
        });
    }

    async fn check_recurring_tasks(db: &DbPool, tx: &Sender<TaskEvent>) -> Result<(), ...> {
        // 1. Query all recurring_template tasks
        // 2. For each, check if a new instance is due
        //    - Compare recurrence interval against last completed_at of latest instance
        //    - Or check next_run_at
        // 3. If due, create a new task with task_type='recurring_instance',
        //    parent_task_id=template_id, status='pending'
        // 4. Send TaskEvent::NewTask
    }
}
```

Recurrence format (unified: value is always minutes):
```json
{"interval": 30}    // every 30 minutes
{"interval": 60}    // every hour
{"interval": 360}   // every 6 hours
{"interval": 1440}  // every 24 hours
```

Scheduler logic: `now() - last_instance.completed_at >= interval * 60 seconds`.

UI presents human-readable labels ("30分钟", "1小时", "6小时", "24小时", "自定义") and sends the integer minutes value to API.

### 4. Agent Runtime Simplification

**File:** `py-agent/agent_runtime.py`

Current: starts heartbeat daemon thread, then enters JSON-RPC stdin loop.

Change: remove `start_heartbeat()` call. Agent becomes purely reactive:

```python
def main():
    provider = make_provider(...)
    agent_id = args.agent_id
    # No more start_heartbeat()

    rpc_server = JSONRPCServer()
    rpc_server.register("ping", handle_ping)
    rpc_server.register("chat", handle_chat)
    rpc_server.register("mailbox_check", handle_mailbox_check)
    rpc_server.run()  # reads stdin, blocking
```

### 5. Heartbeat Service Deprecation

**File:** `py-agent/heartbeat.py`

Removed as a background daemon. The `start_heartbeat()` function and `_heartbeat_loop` are deleted.

The evaluator (`py-agent/evaluator.py`) is retained — it can be used by the agent after executing any task to decide whether to notify the user/requester.

HEARTBEAT.md files are no longer read by agents. They may remain as informational references but are not part of the task system.

### 6. Mailbox → Task Integration

**File:** `src/api/mailbox.rs`

Current: mailbox messages are stored in files, agents poll them via heartbeat.

Change: when a mailbox message is sent (via `POST /api/mailbox/send`), the handler also creates a task for the target agent:

```rust
// After saving the mailbox message:
let task_uuid = Uuid::new_v4().to_string();
let task = NewTask {
    task_uuid: task_uuid.clone(),
    target_agent: target_agent_id,
    source: sender_id,  // source is the sender
    method: "mailbox".into(),
    params: json!({"mailbox_msg_id": msg_id, "content": content}).to_string(),
};
tasks::create_task(&db_pool, &task)?;
task_tx.send(TaskEvent::NewTask { task_uuid })?;
```

This ensures mailbox messages are delivered as tasks through the central system immediately, without agent-side polling.

### 7. Frontend Redesign

**File:** `web-ui/src/pages/Schedule.tsx`

Layout (two sections):

#### Section 1: Per-Agent Queue Cards (top)

Horizontal scrollable card per agent. Each card shows:

- Agent name + status indicator (online/offline/busy - green/yellow/red dot)
- Current running task (highlighted, with "▶" prefix)
- Queued tasks (2-3 shown with "⏳" prefix, remaining count badge)
- Recurring tasks assigned to this agent (with "⏱" prefix and interval label)
- Last heartbeat/last_active timestamp

If agent is offline: dimmed card with "offline" badge.

#### Section 2: Task Timeline (bottom)

Full-width chronological list of all tasks, newest first. Each row shows:

- Status icon: 🟢 completed, 🟡 running, ⏳ pending, 🔴 failed, ⏱ recurring template
- Task description
- Source → target (e.g., "you → 员工A" or "组长 → 员工B")
- Timestamps (created / started / completed)
- Result snippet (completed tasks, truncated)
- Error message (failed tasks)
- For recurring templates: interval label and next run time

Completed tasks are visually dimmed (opacity reduced).

#### Create Task Dialog

Extended from current implementation:

- Task description textarea
- Assign to dropdown (agent list)
- Task type: "一次性" | "周期性"
- If "周期性": interval selector (30m, 1h, 2h, 6h, 12h, 24h, custom)

#### Recurring Task Management

Recurring templates appear in both sections:
- Agent card shows the interval (e.g., "⏱ 每30分钟")
- Timeline shows them with "⏱ 周期" icon
- Clicking a recurring task opens a detail view showing: definition, last run, next run, all past instances

## Implementation Order

1. **Fix schedule proxy** — Python → Rust (fixes "no tasks shown" bug)
2. **Fix task_tx.send()** — Rust schedule handler (fixes "stuck pending" bug)
3. **Extend tasks table** — Add task_type, recurrence, parent_task_id columns
4. **Implement SchedulerService** — Background recurring task checker
5. **Remove heartbeat from agent** — agent_runtime.py cleanup
6. **Mailbox → task integration** — Create tasks on mailbox send
7. **Frontend redesign** — Queue cards + timeline + recurring task UI
8. **Remove legacy schedule.json code** — Cleanup Python routes and heartbeat.py

## Edge Cases

- **Recurring task overdue**: If agent was offline and missed instances, SchedulerService creates only one catch-up instance (not all missed)
- **Recurring task with no instances yet**: Check `recurrence` field + `created_at` to determine first run
- **Mailbox task for offline agent**: Task stays pending in DB, DispatchEngine will push when agent comes back online (AgentManager health check reconnects)
- **Cancelling a recurring template**: Set status to `cancelled`, SchedulerService skips cancelled templates
- **Agent busy with a long task**: DispatchEngine queues tasks per agent — next task starts when current completes

## Files Changed

| File | Change |
|------|--------|
| `web/routes/schedule.py` | Rewrite: proxy to Rust |
| `src/api/schedule.rs` | Add task_tx.send(), add task_type/recurrence to CreateTaskRequest |
| `src/api/router.rs` | Add schedule routes if needed |
| `src/scheduler.rs` | New: SchedulerService |
| `src/main.rs` | Spawn SchedulerService during startup |
| `src/db/pool.rs` | Extend tasks table schema |
| `src/db/tasks.rs` | Add recurring task queries |
| `src/db/models.rs` | Extend Task/NewTask models |
| `src/api/mailbox.rs` | Create task on mailbox send |
| `py-agent/agent_runtime.py` | Remove heartbeat startup |
| `py-agent/heartbeat.py` | Deprecate heartbeat daemon |
| `web-ui/src/api/schedule.ts` | Add recurring task API calls |
| `web-ui/src/pages/Schedule.tsx` | Full redesign (queue cards + timeline) |
| `web-ui/src/i18n/*.ts` | Add new translations |
