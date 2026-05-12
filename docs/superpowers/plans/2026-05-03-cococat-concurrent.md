# Concurrent Tool Execution Plan

**Goal:** When LLM returns multiple tool calls, execute them in parallel instead of sequentially.

**Architecture:** In agent_loop.py, use `concurrent.futures.ThreadPoolExecutor` to run concurrent-safe tools in parallel.

---

### Task 1: Add parallel execution to agent_loop.py

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Add concurrent execution**

In `run()`, find the tool execution loop:

```python
                for tc in tool_calls:
                    result = self.tools.execute(tc["name"], tc.get("arguments", {}))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
```

Replace with parallel execution:

```python
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
                    futures = {}
                    for tc in tool_calls:
                        f = executor.submit(self.tools.execute, tc["name"], tc.get("arguments", {}))
                        futures[f] = tc
                    for f in as_completed(futures):
                        tc = futures[f]
                        try:
                            result = f.result(timeout=60)
                        except Exception as e:
                            result = f"Tool error: {e}"
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result,
                        })
```

Note: Tool results are appended in completion order, not original order. The LLM matches results by `tool_call_id`, so order doesn't matter.

- [ ] **Step 2: Build and test**

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: concurrent tool execution with ThreadPoolExecutor"
```
