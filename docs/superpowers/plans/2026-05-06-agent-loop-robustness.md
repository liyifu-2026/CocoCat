# Agent Loop Robustness Implementation Plan

**Goal:** Fix LLMResponse dict→object mismatch and wire streaming into `agent_loop.py`.

**Files:**
- Modify: `py-agent/agent_loop.py`

---

### Task 1: Fix LLMResponse field access

`LLMResponse` is a dataclass, not a dict. Replace all `.get()` calls with attribute access.

**Changes in `agent_loop.py`:**

| Line | Before | After |
|------|--------|-------|
| 282 | `response.get("content", "")` | `response.content or ""` |
| 283 | `response.get("tool_calls", [])` | `response.tool_calls` |
| 284 | `response.get("reasoning_content")` | `response.reasoning_content` |
| 290-291 | `response.get("usage")` → `u.get(...)` | `response.usage` |
| 295 | `response.get("finish_reason")` | `response.finish_reason` |
| 299-303 | Same pattern in length recovery block | Same fix |
| 304 | `response.get("content", "")` | `response.content or ""` |
| 305 | `response.get("finish_reason")` | `response.finish_reason` |

### Task 2: Wire streaming

Add `chat_stream()` usage so the loop can stream token deltas via `on_progress`.

After line 270, replace:
```python
            content = ""
            tool_calls = []
            reasoning = None
            response = None
            for retry in range(3):
                response = self.llm.chat_with_retry(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                    retry_mode="persistent",
                )
                content = response.get("content", "") or ""
                tool_calls = response.get("tool_calls", []) or []
                reasoning = response.get("reasoning_content")
                if reasoning and on_reasoning:
                    on_reasoning(reasoning)
                if content.strip() or tool_calls:
                    break
```

With:
```python
            content = ""
            tool_calls = []
            reasoning = None
            response = None

            if on_progress and hasattr(self.llm, 'chat_stream'):
                for chunk in self.llm.chat_stream(
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                ):
                    if chunk["type"] == "delta":
                        content += chunk["content"]
                        if on_progress:
                            on_progress(chunk["content"])
                    elif chunk["type"] == "done":
                        if chunk["content"]:
                            content = chunk["content"]
                    elif chunk["type"] == "error":
                        pass
                response = LLMResponse(content=content)
            else:
                for retry in range(3):
                    response = self.llm.chat_with_retry(
                        messages=messages,
                        tools=tool_defs if tool_defs else None,
                        retry_mode="persistent",
                    )
                    content = response.content or ""
                    tool_calls = response.tool_calls
                    reasoning = response.reasoning_content
                    if reasoning and on_reasoning:
                        on_reasoning(reasoning)
                    if content.strip() or tool_calls:
                        break
```

But wait — `chat_stream` is a generator on `LLMProvider`, not on the old `LLMClient`. Since we now use `make_provider()` which returns an `LLMProvider`, `self.llm.chat_stream` should exist. But `chat_stream` doesn't return tool calls or reasoning content — it's a simpler interface. So the streaming path would work for simple responses but not for tool-calling turns.

Let me think about this more carefully. The `chat_stream` method in `OpenAICompatProvider` handles streaming correctly and returns proper `LLMResponse` at the end. But the issue is that `chat_stream` processes one chunk at a time and we lose the ability to inspect tool_calls mid-stream.

For now, the cleanest approach is:
1. Use `chat_stream()` for text-only turns (no tools)
2. Fall back to `chat_with_retry()` when tools are available

Actually, looking at the `chat_stream` implementation in `openai_compat.py`, it already handles tool calls in streaming mode — the SDK sends tool_calls as part of the stream. But our `chat_stream` implementation only extracts delta content, not tool calls.

For simplicity and correctness, let me keep the streaming focused on content deltas and use the non-streaming path when tools are involved:

```python
tool_mode = bool(tool_defs)
if tool_mode:
    # Use non-streaming for tool-calling turns
    response = self.llm.chat_with_retry(...)
else:
    # Use streaming for text-only turns
    for chunk in self.llm.chat_stream(...):
        ...
```

Actually, this is overcomplicating things. Let me just do:
1. Fix the dict→object bug
2. Add streaming as a simple `chat_stream` path for when there are no tools
3. Keep `chat_with_retry` as the default

Let me rewrite the plan more simply.
