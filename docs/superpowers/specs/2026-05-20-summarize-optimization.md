# Summarize Optimization Design

**Date:** 2026-05-20
**Status:** Approved

## Current State

`SummarizeMemory` compresses session messages on a ticker (every 6 turns), saving to
`summaries/{session_id}.json`. The file is read only by the day compile chain — the agent
never sees it. Messages in `run_agent` grow unbounded, eventually exceeding LLM token limits.

## Redesigned Flow

One trigger, one output, two consumers.

```
run_agent: after each LLM turn
  1. Count total tokens in messages array
  2. If token_count > 8000 OR session idle > 30 min:
     a. Identify earliest messages (keep most recent ~3000 tokens as-is)
     b. Load existing summaries/{session_id}.json (if any)
     c. LLM compresses: old_messages + existing_summaries → new summary entry
     d. Append new entry to summaries/{session_id}.json (array, not overwrite)
     e. Insert summary as role:system message at messages[1]
     f. Remove compressed original messages from array
  3. If token_count ≤ 8000 and not idle: skip
```

## Key Decisions

### Compression Object

Not the full session. The earliest messages to be removed + all prior summary entries.
LLM prompt: "Synthesize these into a concise running summary. Keep all key facts,
decisions, user preferences, and project context."

```python
existing_entries = load_json("summaries/{id}.json")  # array of {at, summary}
old_messages = messages[:cutoff]  # messages being removed
new_summary = await llm_compress(old_messages, existing_entries)
```

### Token Threshold

8000 tokens (configurable via `COCOCAT_SUMMARIZE_TOKEN_THRESHOLD`).
When exceeded, compress earliest messages until total < 5000 tokens.

### Idle Trigger

If session has not been modified for > 30 minutes AND has new content since last
summarize, compress regardless of token count. This handles the case where a user
returns to an old conversation — the new content gets compressed for day compile.

### Storage: Cumulative Array

`summaries/{session_id}.json` stores an array, not a single object:

```json
[
  {"at": "2026-05-20T14:30:00", "summary": "Discussed database options: SQLite vs PostgreSQL..."},
  {"at": "2026-05-20T15:00:00", "summary": "Decided on PostgreSQL. User prefers ORM over raw SQL."}
]
```

Each compression run appends a new entry. The file grows over time.
Day compile reads the entire array.

### Day Compile Pickup

Day compile uses `summaries/*.json` mtime (or `.cursor` tracking) to identify
new/modified files since last run. A session file updated days later (user returned
to old conversation) is picked up like any other.

## Prompt Injection

When building messages for the next LLM call:

```python
summaries = load_summary_entries(session_id)
if summaries:
    summary_text = "\n".join(f"[{s['at']}] {s['summary']}" for s in summaries)
    messages.insert(1, {"role": "system", "content": f"## Prior Conversation Summary\n{summary_text}"})
```

## Messages Structure

```
messages = [
  {role: "system", content: config.system_prompt},           # static: agent identity/rules/tools
  {role: "system", content: "## Prior Conversation Summary\n{summaries}"},  # compressed history
  {role: "user", content: "第N-2轮"},                       # recent original (kept as-is)
  {role: "assistant", content: "第N-2轮回复"},
  {role: "user", content: "第N-1轮"},
  {role: "assistant", content: "第N-1轮回复"},
  {role: "user", content: "当前轮"},                         # current input
]
```

## Implementation Plan

### Files to change

1. **`cococat/memory/summarize.py`** — Rewrite: remove ticker, add token-count-based
   `compress_session(messages, session_id) → new_messages` function

2. **`cococat/core/agent.py`** — `run_agent()`: after each iteration, call
   compress_session() if token_count > threshold, rebuild messages array

3. **`cococat/memory/store.py`** — No changes needed (summarize is standalone)

4. **`cococat/memory/compile.py`** — No changes (already reads summaries/ dir)
