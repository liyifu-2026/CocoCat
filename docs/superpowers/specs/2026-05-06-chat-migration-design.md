# Chat Groups Migration: FastAPI JSONL → Rust SQLite

## Problem

The Chat page sends messages that get stored in JSONL files (`chat/groups.json`, `chat/{id}/messages.jsonl`) but never trigger agent processing. Agents have no mechanism to poll or receive these messages. Meanwhile, the Rust core already manages SQLite with a `messages` table that goes unused by the chat system.

## Architecture Change

```
Before:
  Frontend → FastAPI chat_groups.py → JSONL files (store only, no agent)
  Frontend → Rust /api/chat → SQLite (agent processing, but unused by chat page)

After:
  Frontend → FastAPI (proxy) → Rust /api/chat/groups/* → SQLite + agent dispatch
```

FastAPI becomes a thin proxy. All chat logic moves to Rust.

## New Database Tables

```sql
CREATE TABLE IF NOT EXISTS chat_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    announcement TEXT NOT NULL DEFAULT '',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_group_members (
    group_id TEXT NOT NULL REFERENCES chat_groups(id),
    agent_id TEXT NOT NULL REFERENCES agents(id),
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    PRIMARY KEY (group_id, agent_id)
);
```

Messages reuse the existing `messages` table (`chat_group` column stores group_id).

## Rust Modules

### `src/db/chat_groups.rs`
- `create_group()`, `get_group()`, `list_groups()`, `delete_group()`, `update_group()`
- `add_member()`, `remove_member()`
- `send_message()` — inserts to `messages` table + creates task for mentioned agents
- `recall_message()`, `mark_read()`
- `get_messages()`, `get_agent_context()`
- `init_default_group()` — called on startup

### `src/api/chat_groups.rs`
- Full REST handler for all `/api/chat/groups/*` routes

### Message → Agent Flow

`send_message()` in Rust:
1. Insert user message to `messages` table (role=user)
2. Parse `@agent_id` mentions from content
3. For each mentioned agent: create Task, notify DispatchEngine
4. If no mentions but group has members: dispatch to first non-admin member
5. Agent processes → DispatchEngine stores result to `messages` table (role=assistant) via Task completion callback
6. Frontend polls `GET /api/chat/groups/{id}/messages` to see the reply

### Task Params

`send_message()` creates a task with params:
```json
{
  "content": "user message",
  "scene_id": "default",
  "chat_group": "general",
  "source_msg_uuid": "uuid-of-user-message"
}
```

### Task Result → Message

When an agent task completes, the current `process_task()` in `dispatch/engine.rs` calls `tasks::complete_task()`. We add a step here: parse the task's params, if `chat_group` is present, insert the agent's reply as a `messages` row (role=assistant) in the same group, referencing the user message via `msg_uuid` chain.

## FastAPI Changes

`web/routes/chat_groups.py`: replace all file-based logic with `httpx` proxying to `http://localhost:3000/api/chat/groups/...`.

## Startup Initialization

Rust core startup: if no groups exist, create a "General" default group, populate members from `agents` table.

## Cleanup

Old JSONL files (`chat/groups.json`, `chat/{id}/messages.jsonl`) become unused but are not actively deleted — `collaboration.py` still reads `chat/group.jsonl` (separate data). Old files can be cleaned up after full verification.
