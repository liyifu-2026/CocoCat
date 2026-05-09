# CocoCat v2 Implementation Plan

2026-05-09

Based on [architecture spec](../specs/2026-05-09-cococat-architecture-v2.md).

## Guiding Principles

- **Progressive, not rewrite.** Each phase has old + new systems coexisting. Verify before replacing.
- **TDD on core.** EventBus, Agent, Session, AgentPool, tool permission filtering — all test-first.
- **Don't rewrite battle-tested code.** Channel adapters (WeChat/ilink/Feishu) and KB wiki system keep their implementation. Only change their message delivery mechanism.
- **Every phase is independently rollback-able.**

## Phase 0: Cleanup (1-2 days, zero risk)

Delete dead code to reduce cognitive load:

- Uncompiled Rust files in `src/`
- `py-agent/verify_channel.py`, `py-agent/evaluator.py`
- `GET /api/activity` endpoint
- Remove TUI (already done)
- Remove Telegram/Discord channels (already done)

**Success criteria**: `cargo check` still passes on remaining code. Python imports unchanged.

## Phase 1: New Python Core (parallel, 1 week)

New `cococat/` package built alongside existing `py-agent/`. Nothing replaces old code yet.

All modules TDD — test first, then implement.

### 1.1 EventBus (~50 lines)
- `async publish(event_type, data)` / `subscribe(event_type, callback)` / `unsubscribe(event_type, callback)`
- Tests: single subscriber, multiple subscribers, unsubscription, no-subscriber case

### 1.2 Agent class (~100 lines)
- Pure Python object: `id`, `role` (main/sub), `state` (idle/working), `bound_scene`
- `init(system_prompt, tools)` — one-time setup
- `run(message, context) -> str` — creates session, runs agent loop, returns result
- Tests: init builds tools, run returns string, bound_scene changes scope tool list

### 1.3 Session model (~80 lines)
- JSONL read/write (one JSON entry per line)
- Session create, append, close, load
- LRU cache (max 10 active sessions)
- Tests: write → read round-trip, LRU eviction, concurrent sessions

### 1.4 Tools system (~150 lines)
- Flat dict: `{name, description, parameters, execute}`
- All 20 core tools implemented
- Permission filtering: based on agent state (idle=global, working=scene-scoped)
- Tests: idle agent sees all tools, bound agent sees only scene tools

### 1.5 AgentPool (~100 lines)
- Manages multiple Agent instances
- `get_free()`, `bind_to_scene(agent_id, scene_id)`, `unbind(agent_id)`
- Tests: pool size enforcement, bind/unbind cycle, concurrent access

**Success criteria**: All Phase 1 modules pass tests. Importable without breaking old code.

## Phase 2: Replace Rust Infrastructure (3-4 weeks)

Bridge Rust components one at a time, low-risk first.

### 2.1 DB Layer
- Python `sqlite3` + WAL mode
- Read/write existing `cococat.db` schema (no schema changes)
- Tests: query agents/messages/scenes tables, verify data matches Rust queries

### 2.2 FastAPI Routes
- New FastAPI app, listen on port 8000 (Rust stays on 3000)
- Migrate endpoints one at a time. After each, point Web UI to new port, verify, delete Rust version.
- Start with read-only endpoints → write endpoints → streaming endpoints
- Auth: removed (no JWT needed — local tool)

### 2.3 WebSocket
- FastAPI WebSocket + asyncio broadcast via existing EventBus
- Event types: `text_delta`, `thinking_start/delta/end`, `tool_start/end`, `task_assign`, `task_complete`, `agent_state`, `scene_message`, `kb_ingest_progress`, `error`
- Connection lifecycle: connect → `connected` → events → `pong` on ping

### 2.4 Scheduler
- Simple asyncio timer loop (60s)
- Cron task creation/management

**Success criteria**: All Rust endpoints replaced. Rust daemon still running but no traffic to it.

## Phase 3: Replace Agent Runtime (2-3 weeks, highest risk)

Subprocess agents → in-memory Agent objects.

### 3.1 Main AI first
- User-facing chat switches from subprocess to `agent.run()`
- Fastest user feedback loop if something breaks
- Tests: full chat flow end-to-end (message in → agent processes → reply out)

### 3.2 Idle sub AIs
- Main AI task delegation uses `agent.run()` instead of spawning subprocess
- Parallel sub-agent tasks via `asyncio.gather`
- Tests: multi-agent delegation, result aggregation

### 3.3 Scene-bound sub AIs (last)
- Channel messages route to in-memory Agent via EventBus
- **Safety net**: messages persisted to DB before dispatch. If agent crashes, message re-queued on restart.
- Tests: channel message → agent → reply round-trip with crash-recovery simulation

**Success criteria**: Zero subprocess spawns. All agents are Python objects. Scene channel messages survive restart.

## Phase 4: Channel Adapter Migration (2 weeks)

**Do not rewrite** the existing channel implementations in `py-agent/channels/`. They handle real-world platform edge cases.

Only change message delivery:
- Old: `AgentHandle.send_message()` → write `inbox.jsonl` → polling thread reads
- New: `EventBus.publish(scene_message)` → bound Agent directly consumes

Update `on_message` callbacks to publish to EventBus instead of writing to mailbox JSONL.

**Success criteria**: WeChat/ilink/Feishu channels work identically to before. No external user notices the migration.

## Phase 5: Cleanup (1 week)

- Delete `src/` (Rust daemon)
- Delete `web/` (old FastAPI on port 8000 — replaced by new)
- Delete `agents/mailbox/` directory
- Delete `Cargo.toml`
- `start.sh` → `python -m cococat serve`
- Delete all old spec/plan docs except this one and the architecture spec

**Success criteria**: One command starts everything. No Rust. No subprocess agents. No file-based mailbox.

## Testing Strategy

| Phase | Approach |
|-------|----------|
| Phase 1 | Strict TDD. Every module test-first. |
| Phase 2 | Key path TDD (DB queries, WebSocket events). |
| Phase 3 | Integration tests for full chat flow + crash recovery. |
| Phase 4 | Manual verification (external APIs). Fine to skip TDD here. |
| Phase 5 | Smoke test: one command, everything works. |

## Time Estimate

| Phase | Duration |
|-------|----------|
| 0: Cleanup | 1-2 days |
| 1: New Python core | 1 week |
| 2: Replace Rust | 3-4 weeks |
| 3: Replace Agent runtime | 2-3 weeks |
| 4: Channel adapters | 2 weeks |
| 5: Cleanup | 1 week |
| **Total** | **2-3 months** |
