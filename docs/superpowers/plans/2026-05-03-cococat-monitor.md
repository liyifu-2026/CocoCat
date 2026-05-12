# Monitor System Plan

**Goal:** Track LLM token usage and cost per agent per task.

---

### Task 1: Add token tracking to AgentLoop + log to JSONL

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Add usage tracking in run()**

In `run()`, after each LLM call, accumulate token usage. Return it in the result dict.

Replace the empty retry loop:

```python
            for retry in range(3):
                response = self.llm.chat(...)
                ...
                if content.strip() or tool_calls:
                    break
```

After the retry loop, accumulate usage:

```python
            usage = response.get("usage")
            if usage:
                total_input = total_usage.get("input", 0) + usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0) or 0
                total_output = total_usage.get("output", 0) + usage.get("output_tokens", 0) or usage.get("completion_tokens", 0) or 0
                total_usage = {"input": total_input, "output": total_output}
```

- [ ] **Step 2: Log usage after task completes**

After the while loop, before the return, add:

```python
        # Log token usage
        if total_usage.get("input", 0) or total_usage.get("output", 0):
            _log_usage(self.agent_id, prompt, total_usage, iteration)
```

Add the `_log_usage` function after `append_history`:

```python
def _log_usage(agent_id: str, prompt: str, usage: dict, iterations: int):
    """Log token usage to agents/_usage.jsonl."""
    import os, json
    from datetime import datetime
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "_usage.jsonl")
    entry = {
        "timestamp": datetime.now().isoformat(),
        "agent_id": agent_id,
        "prompt_preview": prompt[:100],
        "input_tokens": usage.get("input", 0),
        "output_tokens": usage.get("output", 0),
        "total_tokens": usage.get("input", 0) + usage.get("output", 0),
        "iterations": iterations,
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
```

And add `total_usage = {"input": 0, "output": 0}` before the while loop.

- [ ] **Step 3: Add usage API endpoint to web/main.py**

```python
@app.get("/api/usage")
def get_usage(limit: int = 50):
    """Read recent token usage."""
    usage_path = BASE_DIR / "agents" / "_usage.jsonl"
    entries = []
    if usage_path.exists():
        with open(usage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except: pass
    return {"usage": entries[-limit:]}
```

- [ ] **Step 4: Test**

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/agent_loop.py web/main.py
git commit -m "feat: add token usage tracking and monitor API"
```
