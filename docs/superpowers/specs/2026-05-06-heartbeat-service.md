# Heartbeat Service — CocoCat

## Summary

A periodic daemon that wakes an agent to autonomously process tasks from
`HEARTBEAT.md` and respond to incoming mailbox messages.  Aligned with nanobot's
heartbeat architecture.

## Architecture

```
                  ┌──────────────────────┐
                  │  agent_runtime.py    │
                  │                      │
                  │  start_heartbeat()   │
                  │         │            │
                  │  ┌──────▼────────┐   │
                  │  │ HeartbeatService│  │
                  │  │  (async, own   │  │
                  │  │   event loop,  │  │
                  │  │   daemon thread)│  │
                  │  └──────┬────────┘   │
                  │         │            │
                  │         ▼            │
                  │  asyncio.run()       │
                  └──────────────────────┘
```

## Files

| File | Action | Purpose |
|------|--------|---------|
| `py-agent/heartbeat.py` | Rewrite | `HeartbeatService` class |
| `py-agent/evaluator.py` | New | `evaluate_response()` - LLM notification gate |
| `py-agent/agent_runtime.py` | Edit | Start heartbeat in `main()` before RPC loop |
| `py-agent/tests/test_heartbeat.py` | New | Unit tests |

## HeartbeatService Class

```python
class HeartbeatService:
    def __init__(
        self, *,
        agent_id: str,
        agent_name: str,
        scene: str,
        interval: int = 300,
        provider: LLMProvider,
        model: str,
        on_execute: Callable[[str], str] | None = None,
        on_notify: Callable[[str, str], None] | None = None,
    )

    def start(self) -> None
        # daemon thread -> asyncio.run(self._async_loop())

    def stop(self) -> None
        # set _running = False

    async def async_tick(self) -> None

    async def trigger_now(self, prompt: str | None = None) -> str | None
```

## Tick Flow

```
async_tick():
    # ── Phase 0: HEARTBEAT.md ──
    content = read_heartbeat_file()
    if content:
        action, tasks = await decide(content)
        if action == "run":
            response = on_execute(tasks)
            if response and is_deliverable(response):
                should_notify = evaluate_response(response, tasks, provider, model)
                if should_notify and on_notify:
                    on_notify("admin", response)

    # ── Mailbox (独立处理，跳过 Phase 1) ──
    inbox = read_inbox(agent_id)
    for msg in unread(inbox):
        response = on_execute(msg.content)
        if response and is_deliverable(response):
            should_notify = evaluate_response(response, msg.content, provider, model)
            if should_notify and on_notify:
                on_notify(msg.from, response)
        mark_read(agent_id, idx)
```

## Phases

| Phase | Name | Description |
|-------|------|-------------|
| 0 | Read HEARTBEAT.md | Read `agents/{id}/HEARTBEAT.md` |
| 1 | Decide | LLM virtual tool call: `heartbeat {action: skip|run, tasks?}` |
| 2 | Execute | `on_execute(tasks)` → full AgentRunner.run() |
| 2a | Filter | `_is_deliverable()` blocks canned errors + leaked reasoning |
| 3 | Evaluate | LLM virtual tool call: `evaluate_notification {should_notify}` |
| 4 | Notify | `on_notify(sender, response)` → mailbox send |

Mailbox messages skip Phase 1 (decide) — admin messages are explicit
instructions, not suggestions — but still pass through Filter + Evaluate.

## Virtual Tools

Two LLM tool-call patterns (same as nanobot):

1. **`heartbeat`** — Phase 1 decide
   - `action: skip | run`
   - `tasks: str` (required for run)

2. **`evaluate_notification`** — Phase 3 evaluate
   - `should_notify: bool`
   - `reason: str`

## Callback Contract

```python
on_execute(prompt: str) -> str
    # Wraps AgentRunner.run(prompt)
    # Returns agent response text

on_notify(sender: str, response: str) -> None
    # Wraps mailbox.send_message(sender, agent_id, response)
    # sender is "admin" or another agent_id
```

## Startup Wiring

In `agent_runtime.py:main()`:

```python
from heartbeat import HeartbeatService

provider = make_provider(model=args.model)
agent_id = args.agent_id or "unknown"

def on_execute(prompt: str) -> str:
    runner = AgentRunner(agent_id=agent_id, scene=args.scene_id)
    result = runner.run(prompt)
    return result.get("content", "")

def on_notify(sender: str, response: str) -> None:
    from mailbox import send_message
    send_message(sender, agent_id, response)

hb = HeartbeatService(
    agent_id=agent_id,
    agent_name=agent_id,
    scene=args.scene_id,
    interval=300,
    provider=provider,
    model=args.model,
    on_execute=on_execute,
    on_notify=on_notify,
)
hb.start()
```

## Edge Cases

- HEARTBEAT.md missing/empty → skip Phase 0/1, go directly to mailbox
- Empty response from agent → suppress notification
- Non-deliverable response → suppress notification
- Evaluate failure → default to notify (fail-open)
- Mailbox processing error → skip one message, continue loop
- Thread safe: mailbox uses FileLock, agent files are lock-protected
