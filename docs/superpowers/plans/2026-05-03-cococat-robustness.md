# AgentRunner Robustness Plan

**Goal:** Make the agent runner production-grade with retry logic, multi-provider support, provider fallback, and context governance.

**Architecture:** Redesign `py-agent/llm.py` to support multiple providers with a registry and fallback chain. Add retry with exponential backoff in `agent_loop.py`. Add basic context governance (tool result truncation, message pruning).

---

### Task 1: Redesign LLM client with provider registry + retry

**Files:**
- Modify: `py-agent/llm.py`

- [ ] **Step 1: Rewrite llm.py**

```python
"""Multi-provider LLM client with retry and fallback (nanobot pattern)."""
import json
import os
import time
import random


class LLMResponse:
    def __init__(self, content="", tool_calls=None, finish_reason="stop", reasoning_content=None):
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.reasoning_content = reasoning_content

    def to_dict(self):
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "finish_reason": self.finish_reason,
            "reasoning_content": self.reasoning_content,
        }


class Provider:
    """Base provider interface."""
    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleProvider(Provider):
    def __init__(self, api_key=None, model=None, base_url=None):
        from openai import OpenAI
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        base_url = base_url or os.environ.get("OPENAI_BASE_URL", "")
        self.client = OpenAI(api_key=self.api_key, base_url=base_url or None)

    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7) -> LLMResponse:
        kwargs = dict(model=self.model, messages=self._sanitize(messages), max_tokens=max_tokens, temperature=temperature)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        choice = response.model_dump()["choices"][0]
        message = choice.get("message", {})

        tool_calls = []
        for tc in (message.get("tool_calls") or []):
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {"_error": f"failed to parse: {tc.get('function', {}).get('arguments', '?')}"}
            tool_calls.append({"id": tc["id"], "name": tc["function"]["name"], "arguments": args})

        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            reasoning_content=message.get("reasoning_content"),
        )

    def _sanitize(self, messages):
        allowed = {"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"}
        return [{k: v for k, v in m.items() if k in allowed} for m in messages]


_PROVIDER_SPECS = {
    "deepseek": {
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
}


class LLMClient:
    """Multi-provider client with retry and fallback chain."""

    def __init__(self, providers=None):
        self.providers = providers or []
        if not self.providers:
            # Auto-configure from env
            key = os.environ.get("OPENAI_API_KEY", "")
            model = os.environ.get("LLM_MODEL", "deepseek-v4-flash")
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
            self.providers = [OpenAICompatibleProvider(api_key=key, model=model, base_url=base_url)]

    def chat(self, messages, tools=None, max_tokens=4096, temperature=0.7, max_retries=3) -> dict:
        last_error = None
        for attempt in range(max_retries + 1):
            for provider_idx, provider in enumerate(self.providers):
                try:
                    resp = provider.chat(messages, tools=tools, max_tokens=max_tokens, temperature=temperature)
                    return resp.to_dict()
                except Exception as e:
                    last_error = e
                    if provider_idx < len(self.providers) - 1:
                        continue  # Try next provider
                    if attempt < max_retries:
                        delay = (2 ** attempt) + random.random()
                        time.sleep(delay)
                        continue  # Retry with backoff
        return {"content": f"LLM call failed after {max_retries} retries: {last_error}", "tool_calls": [], "finish_reason": "error"}
```

- [ ] **Step 2: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from llm import LLMClient; c = LLMClient(); print('provider count:', len(c.providers))"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/llm.py
git commit -m "feat: multi-provider LLM client with retry and fallback"
```

---

### Task 2: Add context governance to agent_loop.py

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Add micro-compaction and tool result budgeting**

In `run()`, before the LLM call, add context governance:

```python
            # Context governance (nanobot pattern)
            if iteration > 1 and len(tool_calls) > 0:
                messages = _microcompact_tool_results(messages)
```

Add functions after `auto_dream`:

```python
def _microcompact_tool_results(messages: list[dict], max_tool_chars: int = 2000) -> list[dict]:
    """Truncate verbose tool results to prevent context bloat."""
    result = []
    for msg in messages:
        if msg.get("role") == "tool" and isinstance(msg.get("content"), str):
            content = msg["content"]
            if len(content) > max_tool_chars:
                msg = dict(msg)
                msg["content"] = content[:max_tool_chars] + f"\n...[truncated {len(content) - max_tool_chars} chars]"
        result.append(msg)
    return result
```

- [ ] **Step 2: Build and run**

```bash
cargo build
cargo run
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: add micro-compaction context governance"
```
