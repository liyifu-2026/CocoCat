# AgentRunner Enhancement v2 Plan

**Goal:** (1) Empty response retry + length recovery, (2) Accurate token estimation with tiktoken + context pruning.

---

### Task 1: Empty response retry + length recovery

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Read current agent_loop.py**

Find the `run()` method. After each LLM call, add retry logic for empty responses and length recovery.

Replace:

```python
            response = self.llm.chat(
                messages=messages,
                tools=tool_defs if tool_defs else None,
            )

            content = response.get("content", "") or ""
            tool_calls = response.get("tool_calls", []) or []
            reasoning = response.get("reasoning_content")
```

With:

```python
            # Retry empty responses up to 2 times (nanobot pattern)
            content = ""
            tool_calls = []
            reasoning = None
            for retry in range(3):
                response = self.llm.chat(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                )
                content = response.get("content", "") or ""
                tool_calls = response.get("tool_calls", []) or []
                reasoning = response.get("reasoning_content")
                if content.strip() or tool_calls:
                    break  # Got a real response

            # Length recovery: if truncated, continue to get more
            if response.get("finish_reason") == "length" and content.strip():
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Please continue from where you left off."})
                response = self.llm.chat(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                )
                content += (response.get("content", "") or "")
```

- [ ] **Step 2: Build and test**

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: empty response retry and length recovery"
```

---

### Task 2: Accurate token estimation + context pruning

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Install tiktoken**

```powershell
pip install tiktoken -q
```

- [ ] **Step 2: Replace estimate_tokens with tiktoken**

Replace the `estimate_tokens` function:

```python
import tiktoken

_enc = None
def _get_encoder():
    global _enc
    if _enc is None:
        try:
            _enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _enc = None
    return _enc

def estimate_tokens(text: str) -> int:
    enc = _get_encoder()
    if enc:
        return len(enc.encode(text))
    return len(text) // 4  # fallback
```

- [ ] **Step 3: Add _snip_history function**

Add after `estimate_messages_tokens`:

```python
def _snip_history(messages: list[dict], budget: int = 8000) -> list[dict]:
    """Trim messages to fit within token budget (nanobot _snip_history pattern)."""
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages

    # Keep system prompt, trim from the middle
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    # Keep last 2 messages (recent context), consolidate the rest
    if len(non_system) <= 2:
        return messages

    keep = non_system[-2:]
    to_snip = non_system[:-2]

    # Add a summary marker
    summary = {"role": "system", "content": f"[{len(to_snip)} previous messages snipped for token budget]"}
    result = system_msgs + [summary] + keep

    # If still over budget, just keep system + last message
    if estimate_messages_tokens(result) > budget:
        result = system_msgs + [{"role": "system", "content": "[Earlier conversation trimmed]"}, non_system[-1]]

    return result
```

- [ ] **Step 4: Wire into consolidate()**

In the `consolidate()` function, replace the budget check to use tiktoken:

```python
    current = estimate_messages_tokens(messages)
    if current <= budget:
        return messages
```

- [ ] **Step 5: Add step-by-step file changes**

Read current `C:\Users\12991\Desktop\Cococlaw\py-agent\agent_loop.py`.

1. Add `import tiktoken` at top
2. Replace `estimate_tokens` function with tiktoken version
3. Add `_snip_history` function
4. Add empty response retry + length recovery in `run()`

- [ ] **Step 6: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from agent_loop import estimate_tokens, _snip_history; print('tiktoken:', estimate_tokens('hello world') > 0)"
```

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 7: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: accurate token estimation with tiktoken and context pruning"
```
