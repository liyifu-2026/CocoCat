# Memory System Redesign

**Date:** 2026-05-19
**Status:** Approved

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
  → dream: auto-extracted facts appended at checkpoint
  → agent.remember: manual annotations during conversation
  → agent.forget: remove entries from the board
  → Prompt: ## Working Notes
  → Whiteboard content is fed into day compile → cleared

Layer 3a — Pinned Facts (手工钉选)
  agents/{user}/pinned.md
  → agent.pin: manual permanent facts (append only)
  → agent.unpin: remove by keyword
  → agent.list_pins: list all pinned facts
  → UI: Settings → Pinned Facts tab (per user, view/add/delete)
  → Prompt: ## Pinned Facts
  → Never touched by compile/dream/summarize

Layer 3b — Compiled Memory (自动沉淀)
  agents/{user}/memory/compiled/
    2026-05-19.md          ← daily digest
    2026-05-20.md
    2026-W21.md            ← weekly synthesis
    2026-W22.md
    2026-05-longterm.md    ← monthly archive (single file, overwritten)
    .cursor                ← internal: last-processed markers

  → Prompt: auto-injected — latest 3 day files + latest 2 week files + latest longterm
  → FTS5 indexed for agent.recall search
```

## Session Lifecycle

Sessions are **continuous**, not one-shot. A user can leave and return to the same session.

```
User opens chat page
  → Loads existing session (or creates new if none active)

User chats
  → Messages appended to session.jsonl
  → summarize runs per-turn (ticker threshold)

User idle > 30 minutes
  → Archive checkpoint triggered:
    → If incremental new tokens since last checkpoint ≥ 2000
      → dream extracts facts → appends to memory.md
      → Records new checkpoint position
    → If < 2000, skip
  → Session stays open — user can resume later

User clicks "New Chat" button
  → Current session closed
  → New session created

User reopens page
  → Resumes the same session (does not create a new one)
  → Dream checkpoint logic continues from last position
```

**Dream trigger:** Incremental token count since last checkpoint, not global total. Default threshold 2000 tokens, configurable via `COCOCAT_DREAM_TOKEN_THRESHOLD`.

### Dream Checkpoint Polling

Dream is triggered by a polling loop, not a session-end hook:

```
Cron worker polls every 5 minutes:
  for each sessions/*.jsonl modified > 30 minutes ago:
    read {session_id}.dream_ckpt (last checkpoint line number)
    if exists → count tokens from checkpoint+1 to end
    if not    → count all tokens
    if incremental ≥ 2000 tokens:
      extract facts → append to memory.md
      write new line number to {session_id}.dream_ckpt
```

The `.dream_ckpt` file is a single integer — the last JSONL line number processed.
It lives next to its session file: `sessions/{session_id}.dream_ckpt`.
Service restarts are safe — the checkpoint provides the exact resume position.

## Compile Chain (Cron-triggered)

All three are idempotent — if no new content, they skip silently (zero token cost).

### Day Compile

```
Trigger:  @daily 02:00

Input:    summaries/*.json — only files created since last day compile ran
Output:   compiled/{date}.md — LLM digest in bullet points (max 300 words)

No new summaries → skip
```

### Week Compile

```
Trigger:  @weekly Sunday 03:00

Input:    compiled/{date}.md — only day files created since last week compile ran
Output:   compiled/{year}-W{week}.md — LLM synthesis (max 200 words)

No new day files → skip
```

### Longterm Compile

```
Trigger:  @monthly 1st 04:00

Input:    New week files since last run
          + existing compiled/{month}-longterm.md (as memory background)
Output:   compiled/{month}-longterm.md — OVERWRITTEN, not appended

Algorithm:
  1. Read new week files created since last longterm run
  2. If none → skip
  3. Read existing longterm.md (if any) as "existing knowledge context"
  4. LLM prompt: "Synthesize these new weekly memories into the existing long-term profile.
     Remove redundancies. Keep concrete facts, decisions, user preferences, and project context.
     Existing profile: {old_longterm}
     New observations: {new_week_files}
     Updated profile:"
  5. Write result to longterm.md

Why overwrite: Single file prevents infinite growth. LLM condenses all history
into a bounded profile — old content is not lost, it's re-compressed with new context.
```

## Trigger Matrix

| Trigger | Mechanism | Condition | Action |
|---|---|---|---|
| `summarize` | Per-turn hook | Ticker threshold | LLM compresses session → `summaries/{session_id}.json` |
| `dream` | Poll every 5 min (cron worker) | Session modified > 30 min ago + incremental ≥ 2000 tokens since `.dream_ckpt` | LLM extracts facts → append `memory.md` |
| day compile | Cron `@daily 02:00` | New summaries since last run | LLM reads new summaries → `{date}.md` |
| week compile | Cron `@weekly Sun 03:00` | New day files since last run | LLM reads new day files → `{year}-W{week}.md` |
| longterm compile | Cron `@monthly 1st 04:00` | New week files since last run | LLM: new weeks + old longterm → new `{month}-longterm.md` |
| agent manual | Tool calls | On demand | pin/remember/forget/recall/list_pins |

**Idempotency:** Each step tracks a `.cursor` file recording the last processed item. If a trigger fires with no new content, it skips with zero LLM calls. If one layer fails, downstream layers are unaffected.

## Agent Tools

| Tool | Operates On | Description |
|---|---|---|
| `remember` | `memory.md` (whiteboard) | Append a fact or note to the current whiteboard |
| `forget` | `memory.md` (whiteboard) | Remove matching entries from the whiteboard |
| `pin` | `pinned.md` | Permanently save a fact (append only, survives all processing) |
| `unpin` | `pinned.md` | Remove matching entries from pinned facts |
| `list_pins` | `pinned.md` | List all pinned facts |
| `recall` | Whiteboard + pinned + compiled + FTS5 | Search all memory layers |

**Removed:** `record_experience`, `recall_experience` (covered by pin + compiled memory).

## Cross-Channel Identity Binding

Each user connects channels independently. Memory must route to the right user regardless of which channel the message comes from.

### Database

```sql
CREATE TABLE IF NOT EXISTS channel_identities (
    user_id TEXT NOT NULL,
    channel_type TEXT NOT NULL,      -- "weixin" | "feishu" | "web"
    channel_user_id TEXT NOT NULL,   -- platform-specific user ID
    PRIMARY KEY (channel_type, channel_user_id)
);
```

### Bind Flow

```
User logs into web as "alice"
  → Settings → Channels → "Connect WeChat"
  → Backend generates QR code for WeChat login
  → User scans QR code with WeChat app
  → WeChat callback returns openid
  → Backend: INSERT INTO channel_identities (alice, weixin, openid)

Later, WeChat message arrives:
  → Channel handler receives openid = "wx_abc123"
  → Query: SELECT user_id FROM channel_identities
    WHERE channel_type='weixin' AND channel_user_id='wx_abc123'
  → user_id = "alice"
  → ctx.user_id = "alice"
  → Memory routes to agents/alice/memory/
  → Chat history saved with user_id = "alice"
```

### Unbind

```
User in web settings → Channels → "Disconnect WeChat"
  → DELETE FROM channel_identities
  → Channel connection dropped
  → Memory remains intact at agents/alice/
```

Key: Channel identity binding happens only when the web user is already authenticated.
No unauthenticated channel message can access memory.

## Prompt Injection

```
## Pinned Facts (always remember these)
{pinned.md content — first 2000 chars}

## Recent Memory
{latest 3 day files concatenated}
{latest 2 week files concatenated}
{latest longterm file}

## Working Notes
{memory.md whiteboard — first 3000 chars}
```

Agent does not need to call tools to see its own memory — it's all pre-loaded.

## Frontend

### Chat History Page

```
/chat/history

┌─ 对话历史 ───────────────────────────┐
│  [搜索...________________________]    │
│                                       │
│  05-19 14:30  修 OAuth bug  [alice]  │
│  05-19 10:15  部署文档更新  [bob]    │
│  05-18 16:42  重构用户模块  [alice]  │
└───────────────────────────────────────┘
```

- Each entry shows the first user message as title, timestamp, and user
- Click to expand and read full conversation
- Per-user isolation: Alice only sees her own sessions

### Pinned Facts Tab (Settings)

```
Settings → 钉选事实

┌─ 钉选事实 ────────────────────────────┐
│  [输入事实..._____________] [钉选]    │
│                                       │
│  #1 用户喜欢简洁回答          [✕]    │
│  #2 项目用 SQLite 数据库      [✕]    │
│  #3 部署在 VPS 上             [✕]    │
└───────────────────────────────────────┘
```

- Add fact manually; delete by clicking ✕
- Backed by `agents/{username}/pinned.md`
- Agent's `pin`/`unpin` tools read/write the same file

## File Layout

```
agents/{username}/
  pinned.md                           ← Layer 3a: permanent pinned facts
  memory/
    memory.md                         ← Layer 2: current session whiteboard
    compiled/
      2026-05-19.md                   ← Layer 3b: daily digests
      2026-05-20.md
      2026-W21.md                     ← weekly syntheses
      2026-W22.md
      2026-05-longterm.md             ← monthly archive
      .cursor                         ← internal: last-processed markers
    summaries/
      {session_id}.json               ← per-session ticker summaries
  sessions/
    {session_id}.jsonl             ← Layer 1: raw message logs
    {session_id}.dream_ckpt        ← dream last-processed line number
```

## Migration from Current

1. Existing `memory/memory.md` content is lost (was the whiteboard — expected behavior)
2. Copy `memory/memory.md` to `pinned.md` if users want to preserve existing pins (one-time)
3. No schema migration needed — pure file system changes
4. Cron worker gains three new scheduled tasks for compile chain

## What is NOT Changed

- `summarize` — ticker-based, per-turn, unchanged trigger and logic
- `dream` — trigger updated to incremental token count, core logic unchanged
- `FTS5 facts` — removed from the design (index compiled + pinned content via `recall` instead)
- `kb-agent` and knowledge base — completely separate system, untouched
