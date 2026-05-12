# Consolidator Upgrade Plan

**Goal:** Upgrade consolidator with boundary-aware splitting, multi-round compression, and LLM fallback.

---

### Task 1: Rewrite consolidate()

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Read current consolidate()**

Find the `consolidate()` function in `agent_loop.py`.

- [ ] **Step 2: Replace with upgraded version**

```python
def consolidate(messages: list[dict], llm, budget: int = 8000) -> list[dict]:
    """Upgraded consolidator: boundary-aware, multi-round, fallback."""
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    if len(non_system) < 4:
        return messages

    # Find a safe split point: don't break tool_call+tool_result pairs
    split = max(1, len(non_system) // 2)
    while split > 0:
        msg = non_system[split - 1]
        # Don't split after a tool call (result needs to follow)
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            split += 1
            break
        # Don't split before a tool result
        if msg.get("role") == "tool":
            split -= 1
        else:
            break

    to_consolidate = non_system[:split]
    keep = non_system[split:]

    content_parts = []
    for m in to_consolidate:
        role = m.get("role", "?")
        text = str(m.get("content", ""))[:500]
        if text:
            content_parts.append(f"[{role}] {text}")

    if not content_parts:
        result = system_msgs + keep
        return result if estimate_messages_tokens(result) <= budget * 1.5 else system_msgs + keep[-2:]

    content = "\n\n".join(content_parts)
    prompt = CONSOLIDATION_PROMPT.format(content=content)

    summary = ""
    try:
        response = llm.chat(messages=[{"role": "user", "content": prompt}], max_tokens=256, temperature=0.3)
        summary = (response.get("content") or "").strip()
    except Exception:
        pass

    # Fallback: use text summary if LLM failed
    if not summary:
        summary = f"[Consolidated {len(to_consolidate)} messages: {content[:200]}...]"

    summary_msg = {"role": "system", "content": f"[Consolidated]\n{summary}"}
    result = system_msgs + [summary_msg] + keep

    # Multi-round: if still over budget, recurse
    if estimate_messages_tokens(result) > budget:
        return consolidate(result, llm, budget)

    return result
```

- [ ] **Step 2: Test**

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: upgraded consolidator with boundary-aware, multi-round, fallback"
```
