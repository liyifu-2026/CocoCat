# Memory System Redesign

**Date:** 2026-05-19
**Status:** Draft

## Current State (Broken)

The memory system has 5 sub-systems but only 2 actually run:

| Sub-system | Status | Problem |
|---|---|---|
| `summarize` | ✅ alive | Session summaries via ticker |
| `dream` | ✅ alive | Auto-extract facts from sessions, append to `memory.md` |
| `compile` (day/week/longterm) | ❌ dead code | Never called in production |
| `_assemble` | ❌ dead | Overwrites `memory.md` with today+week+longterm |
| `facts` (FTS5) | ❌ dead | Never called in production |

**Critical bugs:**
- `pin` writes to `memory.md`, but system prompt reads `pinned.md` — different files
- `_assemble()` opens `memory.md` with `"w"` — destroys all pinned/dream content
- `pinned.md` is never written by any code
- No `list_pins` or memory introspection tools

## Redesigned Architecture

### Three Layers (all per-user)

```
Layer 1 — Session Log (原始对话)
  agents/{user}/sessions/*.jsonl
  → summarize: ticker-based compression per turn
  → Prompt: injected as conversation history

Layer 2 — Working Board (会话白板)
  agents/{user}/memory/memory.md
  → dream: auto-extracted facts appended after session (≥50 lines)
  → agent.remember: manual annotations during conversation
  → agent.forget: remove entries from the board
  → Prompt: ## Working Notes
  → Session end → compile day picks important facts → clear board

Layer 3a — Pinned Facts (手工钉选)
  agents/{user}/pinned.md
  → agent.pin: manual permanent facts (append only)
  → agent.unpin: remove by keyword
  → agent.list_pins: list all pinned facts
  → Prompt: ## Pinned Facts
  → Never touched by compile/dream/summarize

Layer 3b — Compiled Memory (自动沉淀)
  agents/{user}/memory/compiled/
    2026-05-19.md          ← daily summary
    2026-05-20.md
    2026-W21.md            ← weekly synthesis
    2026-W22.md
    2026-05-longterm.md    ← monthly archive

  → compile day: cron @daily 02:00, new summaries → daily digest
  → compile week: cron @weekly Sun 03:00, new day files → weekly synthesis
  → compile longterm: cron @monthly 1st 04:00, new week files → longterm archive
  → Each layer only processes content added since last run
  → Prompt: auto-injected — latest 3 day files + latest 2 week files + latest longterm
  → FTS5 indexed for agent.recall search
```

## Trigger Matrix

| Trigger | Mechanism | Condition | Action |
|---|---|---|---|
| `summarize` | Per-turn hook | Ticker threshold (N turns or N tokens) | LLM compresses current session context → `summaries/{session_id}.json` |
| `dream` | Session end (`maybe_trigger_dream`) | Session ≥ 50 lines | LLM extracts facts → append to `memory.md` (whiteboard) |
| day compile | Cron `@daily 02:00` | New summaries since last run | LLM reads new summaries → writes `{date}.md` |
| week compile | Cron `@weekly Sun 03:00` | New day files since last run | LLM reads new day files → writes `{year}-W{week}.md` |
| longterm compile | Cron `@monthly 1st 04:00` | New week files since last run | LLM reads new week files → writes `{year}-{month}-longterm.md` |
| agent manual | Tool calls during conversation | On demand | pin/remember/forget/recall/list_pins |

**Idempotency:** Each compile step tracks a cursor (e.g., "last processed file"). If a trigger fires with no new content, it skips silently. If one layer fails, downstream layers are unaffected — they process whatever IS available.

## Agent Tools

| Tool | Operates On | Description |
|---|---|---|
| `remember` | `memory.md` (whiteboard) | Append a fact or note to the current session's whiteboard |
| `forget` | `memory.md` (whiteboard) | Remove matching entries from the whiteboard |
| `pin` | `pinned.md` | Permanently save a fact (append only, survives sessions) |
| `unpin` | `pinned.md` | Remove matching entries from pinned facts |
| `list_pins` | `pinned.md` | List all pinned facts |
| `recall` | Whiteboard + pinned + compiled + FTS5 | Search all memory layers |

**Removed:** `record_experience`, `recall_experience` (covered by pin + compiled memory).

## Prompt Injection

```
## Pinned Facts (always remember these)
{pinned.md content}

## Recent Memory
{latest 3 day files}
{latest 2 week files}
{latest longterm file}

## Working Notes
{memory.md whiteboard content}
```

Agent does not need to call tools to see its own memory — it's all pre-loaded.

## File Layout

```
agents/{username}/
  pinned.md                        ← Layer 3a: permanent pinned facts
  memory/
    memory.md                      ← Layer 2: current session whiteboard
    compiled/
      2026-05-19.md               ← Layer 3b: daily digests
      2026-05-20.md
      2026-W21.md                  ← weekly syntheses
      2026-W22.md
      2026-05-longterm.md          ← monthly archives
      .cursor                      ← internal: last-processed markers
    summaries/
      {session_id}.json            ← per-session ticker summaries
  sessions/
    {session_id}.jsonl             ← Layer 1: raw message logs
```

## Migration from Current

1. Existing `memory/memory.md` content is lost (was the whiteboard — expected behavior)
2. Copy `memory/memory.md` to `pinned.md` if users want to preserve existing pins (one-time)
3. No schema migration needed — pure file system changes
4. Cron worker gains three new scheduled tasks for compile chain

## What is NOT Changed

- `summarize` — ticker-based, per-turn, unchanged trigger and logic
- `dream` — triggers on session end ≥50 lines, unchanged
- `FTS5 facts` — removed from the design (index compiled + pinned content via `recall` instead)
- `kb-agent` and knowledge base — completely separate system, untouched
