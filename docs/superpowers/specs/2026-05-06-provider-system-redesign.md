# Provider System Redesign

> **Status:** Design approved, pending implementation plan
> **Goal:** Replace monolithic `llm.py` with a modular provider system (aligned with nanobot architecture)
> **Architecture:** ProviderSpec registry → factory auto-detection → per-backend implementation files, with unified retry and streaming built into the base class
> **Tech Stack:** Python 3.10+, `openai` SDK, `anthropic` SDK, `httpx`

---

## Motivation

Current `llm.py` (269 lines) has three problems:
1. **Retry strategy** too simplistic — no transient error detection, no Retry-After parsing, no persistent retry mode
2. **No streaming support** — `chat_stream()` exists but has no integration with the agent loop
3. **Monolithic** — adding a new provider means editing the same file, which encourages skipping it

The reference implementation (nanobot) has a mature provider system with 20+ providers, modular files, and a unified retry layer. We align to this pattern but keep only the providers CocoCat needs.

---

## File Structure

```
py-agent/llm.py                  ← DELETE
py-agent/providers/
├── __init__.py                   # Exports: make_provider, LLMResponse, LLMProvider
├── base.py                       # LLMProvider ABC + LLMResponse + retry core
├── registry.py                   # ProviderSpec registry
├── factory.py                    # make_provider() — auto-detection + creation
├── openai_compat.py              # OpenAI-compatible (DeepSeek, GPT, SiliconFlow, DashScope, Zhipu…)
├── anthropic.py                  # Anthropic Claude native SDK
└── gemini.py                     # Google Gemini (optional, openai_compat covers it)
```

## Component Design

### `providers/registry.py` — Provider Metadata

Single source of truth for every provider. Each provider is a `ProviderSpec` frozen dataclass:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Config field name, e.g. `"deepseek"` |
| `keywords` | `tuple[str,...]` | Model-name keywords for matching, e.g. `("deepseek",)` |
| `env_key` | `str` | Env var name, e.g. `"DEEPSEEK_API_KEY"` |
| `backend` | `str` | Implementation: `"openai_compat"` \| `"anthropic"` \| `"gemini"` |
| `default_api_base` | `str` | Default base URL |
| `supports_streaming` | `bool` | Whether native streaming is supported |

Adding a provider = adding one `ProviderSpec(...)` entry. No code change.

Initial registry covers: DeepSeek, OpenAI, Anthropic, Gemini, SiliconFlow, DashScope, Zhipu.

### `providers/base.py` — Base Class + Retry Core

**`LLMResponse`** (dataclass):
- `content: str | None`
- `tool_calls: list[ToolCallRequest]`
- `finish_reason: str` — `"stop"` / `"tool_calls"` / `"length"` / `"error"`
- `usage: dict` — `{input_tokens, output_tokens}`
- `reasoning_content: str | None`
- Error metadata (for retry, not exception-based):
  - `error_status_code: int | None`
  - `error_type: str | None` — e.g. `"rate_limit"`, `"insufficient_quota"`, `"timeout"`
  - `error_should_retry: bool | None`

**`LLMProvider`** (ABC):
- `chat(messages, tools, model, max_tokens, temperature) → LLMResponse`
- `chat_stream(messages, tools, model, ..., on_content_delta) → LLMResponse` — default fallback to non-streaming
- `chat_with_retry(...)` — built-in retry with:
  - Transient error detection: `_TRANSIENT_ERROR_MARKERS` (429, 5xx, timeout, connection), `_RETRYABLE_STATUS_CODES` (408, 409, 429)
  - Non-retryable detection: `_NON_RETRYABLE_429_ERROR_TOKENS` (insufficient_quota, billing, etc.)
  - `_extract_retry_after()` + `_extract_retry_after_from_headers()` — Retry-After header parsing
  - Exponential backoff with jitter
  - `retry_mode="persistent"` — for heartbeat/background tasks (longer retry, capped at 60s)
  - Image-stripping fallback (strip images and retry when non-transient error with image content)
  - `on_retry_wait` callback for UI feedback during retry waits
- `chat_stream_with_retry(...)` — stream-aware retry

### `providers/factory.py` — Auto-Detection

`make_provider(model="")` creates the right provider from env vars + model name:

1. Parse model prefix: `"deepseek/deepseek-chat"` → name=`"deepseek"`, model=`"deepseek-chat"`
2. Match model name keywords against `ProviderSpec.keywords`
3. Detect from available env vars: check `env_key` for each provider
4. Fallback: OpenAI-compatible with `OPENAI_API_KEY` or no-key (local models)

```python
def make_provider(model: str = "") -> LLMProvider:
    spec = _match_provider(model)
    if spec.backend == "anthropic":
        return AnthropicProvider(api_key=..., model=model)
    elif spec.backend == "gemini":
        return GeminiProvider(api_key=..., model=model)
    else:
        return OpenAICompatProvider(api_key=..., model=model, base_url=...)
```

### `providers/openai_compat.py` — Universal Backend

Covers 90%+ of providers (DeepSeek, GPT, SiliconFlow, DashScope, Zhipu, any OpenAI-compatible API). Core logic adapted from existing `OpenAICompatibleProvider` but:

- Uses `httpx.AsyncClient` instead of synchronous `openai` SDK (async-first)
- Returns `LLMResponse` with error metadata from HTTP status code + response body
- Native streaming via `chat_stream()`
- Sanitizes messages per provider requirements (role alternation, empty content)

### `providers/anthropic.py` — Native SDK

Same as existing `AnthropicProvider` but:
- Uses official `anthropic` SDK
- Adds streaming support
- Error metadata extraction

### `providers/gemini.py` — Google Gemini

Google now offers an OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`), so Gemini can be served by `openai_compat.py`. A separate file is optional.

---

## Caller Migration

| Caller | Change |
|--------|--------|
| `agent_loop.py:6` | `from llm import LLMClient` → `from providers import make_provider` |
| `dream.py:154,237` | Same pattern |
| `tests/test_llm.py` | Delete, replace with `tests/test_providers.py` |

New usage pattern:

```python
# Before:
from llm import LLMClient
client = LLMClient()
result = client.chat(messages, tools=tools)

# After:
from providers import make_provider
provider = make_provider(model="deepseek-chat")
result = provider.chat_with_retry(messages, tools=tools)
```

---

## Dependencies

No new dependencies. Existing deps cover all needs:
- `openai` SDK — for `OpenAICompatProvider`
- `anthropic` SDK — for `AnthropicProvider` (already in requirements)
- `httpx` — for HTTP-based providers

---

## Testing

- `tests/test_providers.py` — unit tests for:
  - ProviderSpec matching logic
  - `make_provider()` auto-detection
  - Transient error detection
  - Retry-after header parsing
  - Each provider's message conversion
- Integration tests (manual): point at real API keys

---

## Migration Path

1. Write `providers/` files in parallel (no callers yet)
2. Write `tests/test_providers.py`
3. Run tests, verify
4. Update `agent_loop.py` and `dream.py` imports
5. Delete `llm.py` and `tests/test_llm.py`
6. Full test suite
