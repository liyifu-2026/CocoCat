# Consolidator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** When an agent's message history exceeds a token budget, the Consolidator compresses old messages into a summary and removes them from the active context. This prevents runaway context windows on long multi-tool-call tasks.

**Architecture:** After each tool call iteration, the agent loop estimates token count. If over budget, it selects old message pairs (user+assistant, tool call+result), asks LLM to summarize, replaces them with a single condensed message.

---

### Task 1: Implement Consolidator in agent_loop.py

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Add token estimation and consolidation**

Add to agent_loop.py. After the `auto_dream` function:

```python
import re

# Rough token estimation (chars / 4)
def estimate_tokens(text: str) -> int:
    return len(text) // 4

def estimate_messages_tokens(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        text = json.dumps(msg, ensure_ascii=False)
        total += estimate_tokens(text)
    return total


CONSOLIDATION_PROMPT = """Summarize the following conversation turn in 1-2 sentences. Focus on what was asked, what tool was used, and what result was obtained.

## Content
{content}

## Summary
"""


def consolidate(messages: list[dict], llm, budget: int = 8000) -> list[dict]:
    """Compress old messages when over budget (nanobot Consolidator pattern)."""
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages

    # Find earliest message pairs to consolidate
    # Keep: system prompt + most recent user message
    # Consolidate: everything between
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) < 4:
        return messages  # Not enough to consolidate

    # Take oldest half of non-system messages for consolidation
    split = len(non_system) // 2
    to_consolidate = non_system[:split]
    keep = non_system[split:]

    # Build content for LLM summarization
    content_parts = []
    for m in to_consolidate:
        role = m.get("role", "?")
        text = str(m.get("content", ""))[:500]
        if text:
            content_parts.append(f"[{role}] {text}")

    if not content_parts:
        return system_msgs + keep

    content = "\n\n".join(content_parts)
    prompt = CONSOLIDATION_PROMPT.format(content=content)

    try:
        response = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.3,
        )
        summary = (response.get("content") or "").strip()
    except Exception:
        summary = f"[Consolidated {len(to_consolidate)} messages]"

    # Replace consolidated block with summary
    summary_msg = {
        "role": "system",
        "content": f"[Consolidated Context]\n{summary}",
    }

    result = system_msgs + [summary_msg] + keep
    saved = current - estimate_messages_tokens(result)
    return result
```

- [ ] **Step 2: Add consolidation trigger in run()**

In `run()`, before the LLM call, add consolidation check. Find the line `response = self.llm.chat(` and add before it:

```python
            # Consolidate if over budget
            if iteration > 1:
                messages = consolidate(messages, self.llm, budget=8000)
```

- [ ] **Step 3: Build and test**

```bash
cargo build
```

Quick Python test:
```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from agent_loop import estimate_messages_tokens, consolidate; print('consolidator import ok')"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: add consolidator with token budget compression"
```

---

### Task 2: Log consolidation events to history

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Log when consolidation happens**

In `consolidate()`, before the return, add a log entry:

```python
    # Log consolidation event
    from datetime import datetime
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": "consolidation",
        "messages_before": len(to_consolidate),
        "tokens_saved": saved,
    }
    # Append to .consolidation_log (for monitoring)
    log_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "agents", "_consolidation_log.jsonl"
    )
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
```

- [ ] **Step 2: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: log consolidation events to file"
```

---

### Task 3: Verify

**Files:**
- No changes needed

- [ ] **Step 1: Run with high-iteration task**

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
cargo build
cargo run
```

- [ ] **Step 2: Check consolidation log**

```powershell
Get-Content "C:\Users\12991\Desktop\Cococlaw\agents\_consolidation_log.jsonl" -ErrorAction SilentlyContinue
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: consolidator verified working"
```

---

## Summary

After this phase:
- ✅ Token estimation per message list
- ✅ Automatic consolidation when over 8K token budget
- ✅ LLM summarizes old message pairs
- ✅ Consolidation events logged for monitoring
