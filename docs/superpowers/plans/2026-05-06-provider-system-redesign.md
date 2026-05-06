# Provider System Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace monolithic `llm.py` with a modular provider system (registry → factory → per-backend files) with unified retry and streaming.

**Architecture:** Six new files in `py-agent/providers/`: registry (metadata), base (ABC + retry core), factory (auto-detection), and 2 backend implementations (openai_compat covers 90%, anthropic is native SDK). All synchronous to match existing `agent_loop.py` — no async. Callers switch from `LLMClient` to `make_provider().chat_with_retry()`. Old `llm.py` deleted.

**Tech Stack:** Python 3.10+, `httpx` (sync client), `openai` SDK, `anthropic` SDK

---

## File Structure

```
Create: py-agent/providers/__init__.py    — package + exports
Create: py-agent/providers/base.py        — LLMProvider ABC + LLMResponse + retry core
Create: py-agent/providers/registry.py    — ProviderSpec registry + lookup helpers
Create: py-agent/providers/factory.py     — make_provider() auto-detection
Create: py-agent/providers/openai_compat.py — OpenAI-compatible (DeepSeek/GPT/SiliconFlow/…)
Create: py-agent/providers/anthropic.py   — Anthropic Claude native SDK
Create: tests/test_providers.py           — unit tests for registry, base, factory
Modify: py-agent/agent_loop.py:6          — switch import + usage
Modify: py-agent/dream.py:154,237         — switch import + usage
Delete: py-agent/llm.py
Delete: py-agent/tests/test_llm.py
```

---

### Task 1: Core types — `registry.py` + `__init__.py`

**Files:**
- Create: `py-agent/providers/__init__.py`
- Create: `py-agent/providers/registry.py`

- [ ] **Step 1: Create provider package**

```bash
mkdir -p py-agent/providers
```

- [ ] **Step 2: Write `py-agent/providers/__init__.py`**

```python
from .base import LLMProvider, LLMResponse, ToolCallRequest
from .factory import make_provider
```

- [ ] **Step 3: Write `py-agent/providers/registry.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    keywords: tuple[str, ...]
    env_key: str
    display_name: str = ""
    backend: str = "openai_compat"
    default_api_base: str = ""
    supports_streaming: bool = False


PROVIDERS: list[ProviderSpec] = [
    ProviderSpec("deepseek",    ("deepseek",),           "DEEPSEEK_API_KEY",    "DeepSeek",    "openai_compat", "https://api.deepseek.com",                  supports_streaming=True),
    ProviderSpec("openai",      ("openai", "gpt"),       "OPENAI_API_KEY",      "OpenAI",      "openai_compat", "https://api.openai.com/v1",                   supports_streaming=True),
    ProviderSpec("anthropic",   ("anthropic", "claude"), "ANTHROPIC_API_KEY",   "Anthropic",   "anthropic",     "https://api.anthropic.com",                   supports_streaming=True),
    ProviderSpec("gemini",      ("gemini", "gemma"),     "GEMINI_API_KEY",      "Gemini",      "openai_compat", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    ProviderSpec("siliconflow", ("siliconflow",),        "SILICONFLOW_API_KEY", "SiliconFlow", "openai_compat", "https://api.siliconflow.cn/v1",              supports_streaming=True),
    ProviderSpec("dashscope",   ("qwen", "dashscope"),   "DASHSCOPE_API_KEY",   "DashScope",   "openai_compat", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    ProviderSpec("zhipu",       ("zhipu", "glm"),        "ZHIPUAI_API_KEY",     "Zhipu",       "openai_compat", "https://open.bigmodel.cn/api/paas/v4"),
]


def find_by_name(name: str) -> ProviderSpec | None:
    for spec in PROVIDERS:
        if spec.name == name:
            return spec
    return None


def find_by_model(model: str) -> ProviderSpec | None:
    lower = model.lower()
    for spec in PROVIDERS:
        for kw in spec.keywords:
            if kw in lower:
                return spec
    return None


def find_by_env() -> ProviderSpec | None:
    for spec in PROVIDERS:
        if spec.env_key and os.environ.get(spec.env_key):
            return spec
    return None
```

- [ ] **Step 4: Run import check**

```bash
python3 -c "from providers.registry import PROVIDERS, find_by_name; print(f'{len(PROVIDERS)} providers loaded')"
```

Expected: `7 providers loaded`

---

### Task 2: Base class — `base.py`

**Files:**
- Create: `py-agent/providers/base.py`

- [ ] **Step 1: Write `py-agent/providers/base.py`**

```python
from __future__ import annotations

import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning_content: str | None = None
    error_status_code: int | None = None
    error_type: str | None = None
    error_should_retry: bool | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def should_execute_tools(self) -> bool:
        if not self.has_tool_calls:
            return False
        return self.finish_reason in ("tool_calls", "stop")


@dataclass(frozen=True)
class GenerationSettings:
    temperature: float = 0.7
    max_tokens: int = 4096
    reasoning_effort: str | None = None


class LLMProvider(ABC):
    generation: GenerationSettings = GenerationSettings()

    _CHAT_RETRY_DELAYS = (1, 2, 4)
    _TRANSIENT_ERROR_MARKERS = (
        "429", "rate limit", "500", "502", "503", "504",
        "overloaded", "timeout", "timed out", "connection",
        "server error", "temporarily unavailable",
    )
    _RETRYABLE_STATUS_CODES = frozenset({408, 409, 429})
    _NON_RETRYABLE_TOKENS = frozenset({
        "insufficient_quota", "quota_exceeded",
        "billing_hard_limit_reached", "insufficient_balance",
        "payment_required",
    })

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        ...

    def chat_stream(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
        """Default: yield full response as a single delta. Override for true streaming."""
        response = self.chat(
            messages=messages, tools=tools, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )
        if response.content:
            yield {"type": "delta", "content": response.content}
        yield {"type": "done", "content": response.content or ""}

    @classmethod
    def _is_transient(cls, response: LLMResponse) -> bool:
        if response.error_should_retry is not None:
            return response.error_should_retry
        if response.error_status_code:
            if response.error_status_code == 429:
                return cls._is_retryable_429(response)
            if response.error_status_code in cls._RETRYABLE_STATUS_CODES or response.error_status_code >= 500:
                return True
        err = (response.content or "").lower()
        return any(m in err for m in cls._TRANSIENT_ERROR_MARKERS)

    @classmethod
    def _is_retryable_429(cls, response: LLMResponse) -> bool:
        type_val = (response.error_type or "").lower()
        if any(t in type_val for t in cls._NON_RETRYABLE_TOKENS):
            return False
        content = (response.content or "").lower()
        if any(t in content for t in cls._NON_RETRYABLE_TOKENS):
            return False
        return True

    @classmethod
    def _extract_retry_after(cls, content: str | None) -> float | None:
        if not content:
            return None
        text = content.lower()
        patterns = (
            r"retry after\s+(\d+(?:\.\d+)?)",
            r"try again in\s+(\d+(?:\.\d+)?)",
            r"retry[_-]?after[\"'\s:=]+(\d+(?:\.\d+)?)",
        )
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return max(0.1, float(m.group(1)))
        return None

    def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        retry_mode: str = "standard",
    ) -> LLMResponse:
        attempt = 0
        delays = list(self._CHAT_RETRY_DELAYS)
        last_response: LLMResponse | None = None

        while True:
            attempt += 1
            try:
                response = self.chat(
                    messages=messages, tools=tools, model=model,
                    max_tokens=max_tokens, temperature=temperature,
                )
            except Exception as e:
                response = LLMResponse(
                    content=f"LLM call error: {e}",
                    finish_reason="error",
                    error_type="exception",
                    error_should_retry=True,
                )

            if response.finish_reason != "error":
                return response

            last_response = response

            if not self._is_transient(response):
                return response

            if retry_mode != "persistent" and attempt > len(delays):
                break

            base_delay = delays[min(attempt - 1, len(delays) - 1)]
            delay = self._extract_retry_after(response.content) or base_delay
            delay = delay + random.random()
            time.sleep(delay)

        return last_response if last_response else LLMResponse(content="LLM call failed", finish_reason="error")
```

- [ ] **Step 2: Run import check**

```bash
python3 -c "from providers.base import LLMProvider, LLMResponse, ToolCallRequest; print('base OK')"
```

Expected: `base OK`

---

### Task 3: OpenAI-compatible provider — `openai_compat.py`

**Files:**
- Create: `py-agent/providers/openai_compat.py`

- [ ] **Step 1: Write `py-agent/providers/openai_compat.py`**

```python
from __future__ import annotations

import json
from typing import Any

import httpx

from .base import LLMProvider, LLMResponse, ToolCallRequest


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
        extra_headers: dict[str, str] | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/") or "https://api.deepseek.com"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=120.0)

    @staticmethod
    def _sanitize(messages: list[dict]) -> list[dict]:
        allowed = {"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"}
        return [{k: v for k, v in m.items() if k in allowed} for m in messages]

    def _build_error_response(self, status: int, body: dict | str) -> LLMResponse:
        error_data = body.get("error", {}) if isinstance(body, dict) else {}
        err_type = error_data.get("type", "") if isinstance(error_data, dict) else ""
        err_msg = error_data.get("message", str(body)) if isinstance(error_data, dict) else str(body)
        return LLMResponse(
            content=f"API error {status}: {err_msg}",
            finish_reason="error",
            error_status_code=status,
            error_type=err_type,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        body = {
            "model": model or self.model,
            "messages": self._sanitize(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            resp = self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            return LLMResponse(content=f"Timeout: {e}", finish_reason="error", error_type="timeout", error_should_retry=True)
        except httpx.RequestError as e:
            return LLMResponse(content=f"Connection error: {e}", finish_reason="error", error_type="connection", error_should_retry=True)

        if resp.status_code != 200:
            try:
                err_body = resp.json()
            except Exception:
                err_body = resp.text
            return self._build_error_response(resp.status_code, err_body)

        data = resp.json()
        choice = data["choices"][0]
        message = choice.get("message", {})
        finish = choice.get("finish_reason", "stop")

        tool_calls = []
        for tc in message.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"]["arguments"])
            except (json.JSONDecodeError, KeyError):
                args = {"_error": f"parse failed: {tc.get('function', {}).get('arguments', '?')}"}
            tool_calls.append(ToolCallRequest(
                id=tc["id"], name=tc["function"]["name"], arguments=args,
            ))

        usage = data.get("usage", {})
        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=finish,
            usage={"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)},
            reasoning_content=message.get("reasoning_content"),
        )

    def chat_stream(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7):
        body = {
            "model": model or self.model,
            "messages": self._sanitize(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        try:
            with self._client.stream("POST", "/chat/completions", json=body) as resp:
                if resp.status_code != 200:
                    yield {"type": "error", "content": f"Stream error {resp.status_code}: {resp.text[:200]}"}
                    return

                content_parts = []
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if not chunk.get("choices"):
                        continue
                    delta = chunk["choices"][0].get("delta", {})
                    if delta.get("content"):
                        content_parts.append(delta["content"])
                        yield {"type": "delta", "content": delta["content"]}

                yield {"type": "done", "content": "".join(content_parts)}
        except (httpx.TimeoutException, httpx.RequestError) as e:
            yield {"type": "error", "content": str(e)}
```

---

### Task 4: Anthropic provider — `anthropic.py`

**Files:**
- Create: `py-agent/providers/anthropic.py`

- [ ] **Step 1: Write `py-agent/providers/anthropic.py`**

```python
from __future__ import annotations

from typing import Any

import httpx

from .base import LLMProvider, LLMResponse, ToolCallRequest


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-20250514"
        self.base_url = base_url.rstrip("/") or "https://api.anthropic.com"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    def _to_anthropic_messages(self, messages: list[dict]) -> list[dict]:
        result = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            tc = m.get("tool_calls")
            tcid = m.get("tool_call_id")
            if role == "tool":
                result.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tcid, "content": content}]})
            elif tc:
                blocks = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for t in tc:
                    blocks.append({"type": "tool_use", "id": t["id"], "name": t["name"], "input": t.get("arguments", {})})
                result.append({"role": "assistant", "content": blocks})
            else:
                result.append({"role": role, "content": content})
        return result

    def _to_anthropic_tools(self, tools: list[dict]) -> list[dict]:
        result = []
        for t in tools:
            fn = t.get("function", t)
            result.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return result

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        body = {
            "model": model or self.model,
            "messages": self._to_anthropic_messages(messages),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = self._to_anthropic_tools(tools)

        try:
            resp = self._client.post("/v1/messages", json=body)
        except httpx.TimeoutException as e:
            return LLMResponse(content=f"Timeout: {e}", finish_reason="error", error_type="timeout", error_should_retry=True)
        except httpx.RequestError as e:
            return LLMResponse(content=f"Connection error: {e}", finish_reason="error", error_type="connection", error_should_retry=True)

        if resp.status_code != 200:
            try:
                err = resp.json()
                err_type = err.get("error", {}).get("type", "")
            except Exception:
                err_type = ""
            return LLMResponse(
                content=f"API error {resp.status_code}: {resp.text[:200]}",
                finish_reason="error",
                error_status_code=resp.status_code,
                error_type=err_type,
            )

        data = resp.json()
        content = ""
        tool_calls = []
        stop_reason = data.get("stop_reason", "end_turn")
        finish = "stop"
        if stop_reason == "tool_use":
            finish = "tool_calls"
        elif stop_reason == "max_tokens":
            finish = "length"

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCallRequest(
                    id=block["id"], name=block["name"], arguments=block.get("input", {}),
                ))

        usage = data.get("usage", {})
        return LLMResponse(
            content=content, tool_calls=tool_calls, finish_reason=finish,
            usage={"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)},
        )
```

---

### Task 5: Factory — `factory.py`

**Files:**
- Create: `py-agent/providers/factory.py`

- [ ] **Step 1: Write `py-agent/providers/factory.py`**

```python
from __future__ import annotations

import os

from .base import LLMProvider
from .registry import find_by_model, find_by_env, ProviderSpec


def _get_env(spec: ProviderSpec) -> str:
    return os.environ.get(spec.env_key, "")


def _find_first_available() -> ProviderSpec | None:
    from .registry import PROVIDERS
    for spec in PROVIDERS:
        if _get_env(spec):
            return spec
    return None


def make_provider(model: str = "") -> LLMProvider:
    spec = find_by_model(model) if model else None
    if not spec:
        spec = find_by_env()
    if not spec:
        spec = _find_first_available()
    if not spec:
        from .registry import PROVIDERS
        spec = PROVIDERS[0]

    api_key = _get_env(spec) or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", spec.default_api_base)

    if spec.backend == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model, base_url=base_url)

    from .openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(api_key=api_key, model=model, base_url=base_url)
```

- [ ] **Step 2: Run import check**

```bash
python3 -c "from providers import make_provider; p = make_provider('deepseek-chat'); print(type(p).__name__)"
```

Expected: `OpenAICompatProvider`

---

### Task 6: Tests — `test_providers.py`

**Files:**
- Create: `tests/test_providers.py`

- [ ] **Step 1: Write `tests/test_providers.py`**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py-agent"))

import pytest
from providers.base import LLMResponse, ToolCallRequest
from providers.registry import find_by_name, find_by_model, PROVIDERS


class TestRegistry:
    def test_find_by_name(self):
        spec = find_by_name("deepseek")
        assert spec is not None
        assert spec.name == "deepseek"

    def test_find_by_name_nonexistent(self):
        assert find_by_name("nonexistent") is None

    def test_find_by_model(self):
        spec = find_by_model("deepseek-chat")
        assert spec is not None
        assert spec.name == "deepseek"

    def test_find_by_model_anthropic(self):
        spec = find_by_model("claude-sonnet-4")
        assert spec is not None
        assert spec.name == "anthropic"

    def test_find_by_model_gpt(self):
        spec = find_by_model("gpt-4o")
        assert spec is not None
        assert spec.name == "openai"

    def test_find_by_model_no_match(self):
        assert find_by_model("xyz-unknown-model-999") is None

    def test_all_providers_have_env_key_and_base(self):
        for spec in PROVIDERS:
            assert spec.env_key, f"{spec.name} missing env_key"
            assert spec.default_api_base, f"{spec.name} missing default_api_base"


class TestLLMResponse:
    def test_no_tool_calls(self):
        r = LLMResponse(content="hello")
        assert not r.has_tool_calls

    def test_has_tool_calls(self):
        r = LLMResponse(content="", tool_calls=[ToolCallRequest(id="1", name="test", arguments={})])
        assert r.has_tool_calls

    def test_should_execute_tools(self):
        r = LLMResponse(content="", tool_calls=[ToolCallRequest(id="1", name="test", arguments={})], finish_reason="tool_calls")
        assert r.should_execute_tools

    def test_should_not_execute_tools_on_error(self):
        r = LLMResponse(content="error", finish_reason="error")
        assert not r.should_execute_tools

    def test_should_not_execute_tools_no_tool_calls(self):
        r = LLMResponse(content="hello", finish_reason="stop")
        assert not r.should_execute_tools


class TestTransientDetection:
    def test_429_is_transient(self):
        from providers.base import LLMProvider
        r = LLMResponse(content="", finish_reason="error", error_status_code=429, error_type="rate_limit_error")
        assert LLMProvider._is_transient(r)

    def test_quota_is_not_transient(self):
        from providers.base import LLMProvider
        r = LLMResponse(content="", finish_reason="error", error_status_code=429, error_type="insufficient_quota")
        assert not LLMProvider._is_transient(r)

    def test_500_is_transient(self):
        from providers.base import LLMProvider
        r = LLMResponse(content="server error", finish_reason="error", error_status_code=500)
        assert LLMProvider._is_transient(r)

    def test_timeout_text_is_transient(self):
        from providers.base import LLMProvider
        r = LLMResponse(content="upstream timeout error", finish_reason="error", error_type="timeout")
        assert LLMProvider._is_transient(r)


class TestRetryAfter:
    def test_extract_seconds(self):
        from providers.base import LLMProvider
        val = LLMProvider._extract_retry_after("retry after 5 seconds")
        assert val is not None and 4.9 <= val <= 5.1

    def test_extract_variant(self):
        from providers.base import LLMProvider
        val = LLMProvider._extract_retry_after('"retry_after": 10')
        assert val is not None and 9.9 <= val <= 10.1

    def test_no_match(self):
        from providers.base import LLMProvider
        assert LLMProvider._extract_retry_after("hello world") is None


class TestChatStream:
    def test_default_stream_fallback(self):
        from providers.base import LLMProvider
        provider = LLMProvider()
        results = list(provider.chat_stream([{"role": "user", "content": "hi"}]))
        assert len(results) >= 1
        assert results[-1]["type"] == "done"
```

- [ ] **Step 2: Run tests**

```bash
python3 -m pytest tests/test_providers.py -v
```

Expected: All pass.

---

### Task 7: Migrate callers + delete old files

**Files:**
- Modify: `py-agent/agent_loop.py:6`
- Modify: `py-agent/dream.py:154,237`
- Delete: `py-agent/llm.py`
- Delete: `py-agent/tests/test_llm.py`

- [ ] **Step 1: Update `agent_loop.py`**

Change line 6:
```python
# Before:
from llm import LLMClient

# After:
from providers import make_provider
```

Update the `LLMClient` initialization (find `self.llm = LLMClient()` or similar):
```python
# Before:
self.llm = LLMClient()

# After:
self.llm = make_provider()
```

Update chat calls — `client.chat(...)` → `self.llm.chat_with_retry(...)`:
```python
# Before:
response = self.llm.chat(messages=[...], max_tokens=256, temperature=0.3)

# After:
response = self.llm.chat_with_retry(messages=[...], max_tokens=256, temperature=0.3, retry_mode="persistent")
```

- [ ] **Step 2: Update `dream.py`** (same pattern, 2 occurrences)

- [ ] **Step 3: Delete old files**

```bash
rm py-agent/llm.py py-agent/tests/test_llm.py
```

- [ ] **Step 4: Run full test suite**

```bash
python3 -m pytest tests/ -v --ignore=tests/test_agent_loop.py --ignore=tests/test_memory_hierarchy.py --ignore=tests/test_per_user_dream.py --ignore=tests/test_web_auth.py
```

Expected: All passing (excluding pre-existing failures).

- [ ] **Step 5: Commit**

```bash
git add py-agent/providers/ tests/test_providers.py py-agent/agent_loop.py py-agent/dream.py
git rm py-agent/llm.py py-agent/tests/test_llm.py
git commit -m "refactor: modular provider system with unified retry and streaming"
```
