# Model Catalog & Token Usage Tracking

Date: 2026-05-16

## Overview

Two related improvements to CocoCat's LLM provider subsystem:

1. **Model Catalog**: Replace sparse, provider-dependent model discovery with modelpedia as the authoritative catalog (4263 models, 30+ providers), while retaining user-enabled model filtering.
2. **Token Usage Logging**: Instrument provider classes to extract and log structured `usage` data from LLM API responses, future-proofing for cost tracking.

## Current State

- `config/models.json`: Manually curated per-provider enabled model lists. Currently only `deepseek-reasoner` and `deepseek-chat` for DeepSeek.
- `POST /api/providers/fetch-models`: Queries `{base_url}/models` per provider. Inconsistent across providers (some require auth, some don't have the endpoint, formats vary).
- No model metadata (context window, pricing, capabilities, lifecycle status) displayed anywhere in UI.
- No token usage tracking whatsoever.

## Design

### 1. Frontend: Model Catalog Layer

**New file**: `web-ui/src/lib/model-catalog.ts`

Provider ID mapping from CocoCat internal names to modelpedia provider IDs:

| CocoCat | modelpedia |
|---------|------------|
| `openai` | `openai` |
| `anthropic` | `anthropic` |
| `deepseek` | `deepseek` |
| `gemini` | `google` |
| `dashscope` | `alibaba` |
| `moonshot` | `moonshot` |
| `minimax` | `minimax` |
| `mistral` | `mistral` |
| `groq` | `groq` |
| `xai` | `xai` |
| `together` | `together` |
| `fireworks` | `fireworks` |
| `deepinfra` | `deepinfra` |
| `cerebras` | `cerebras` |
| `openrouter` | `openrouter` |
| `cohere` | `cohere` |
| `perplexity` | `perplexity` |
| `replicate` | `replicate` |
| `huggingface` | `huggingface` |
| `ollama` | `ollama` |
| `azure` | `azure` |
| `aws-bedrock` | `amazon` |

Providers NOT covered by modelpedia (fall back to `fetch-models`): `siliconflow`, `zhipu`, `doubao`, `baichuan`, `lmstudio`, `llamacpp`, `custom`.

**Exported functions**:

```typescript
getProviderModels(cocoName: string): ModelpediaModel[]
// Returns all non-deprecated models for a provider from modelpedia

getModelMeta(provider: string, modelId: string): ModelpediaModel | undefined
// Returns full metadata for a single model

isProviderSupported(cocoName: string): boolean
// Whether modelpedia covers this provider
```

**Modified**: `web-ui/src/components/settings/ProvidersTab.tsx` → `ProviderDetailPanel`

- Left column ("Available models"): data source switches from backend `available` to modelpedia `getProviderModels()`. Falls back to backend `available` if modelpedia doesn't cover the provider.
- Right column ("Enabled models"): unchanged, still driven by backend `enabled` list.
- Each model entry gains: hover tooltip with context window, pricing, capabilities; status badge (active/deprecated/preview); successor hint for deprecated models.
- "Fetch from API" button: results merged into model list with dedup, but do not replace modelpedia as primary source.
- Search/filter input for the available models list.

### 2. Backend: API Simplification

**Modified**: `cococat/routes/providers.py` → `GET /providers/{name}/models`

- Remove `available` field from response (frontend no longer consumes it).
- Response becomes only `{enabled: string[], default: string}`.

### 3. Backend: Token Usage Logging

**New file**: `cococat/providers/usage.py`

```python
@dataclass
class TokenUsage:
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    provider: str
    duration_ms: float
```

`log_usage(usage: TokenUsage)` outputs structured JSON log at INFO level, keyed for future log aggregation.

**Modified**: `cococat/providers/openai_compat.py`

In both `chat()` and `chat_stream()`: after receiving the API response, extract `response["usage"]` → construct `TokenUsage` → call `log_usage()`. Measure wall-clock duration with `time.monotonic()`.

**Modified**: `cococat/providers/anthropic.py`

In `chat()`: extract `response["usage"]` (Anthropic returns `{"input_tokens": N, "output_tokens": N}`) → construct `TokenUsage` → call `log_usage()`. `chat_stream()` is not yet implemented for Anthropic (falls back to `chat()`).

**Log format** (one line per request):

```json
{"model": "deepseek-v4-flash", "prompt_tokens": 1234, "completion_tokens": 567, "total_tokens": 1801, "provider": "deepseek", "duration_ms": 2340.5}
```

## Non-Goals

- No database table for token usage (deferred per user decision).
- No per-agent or per-user aggregation in this iteration.
- No modelpedia data sync to backend (frontend-only integration).

## Dependencies

- `npm install modelpedia` (web-ui)
- No new Python dependencies.

## Risks

- modelpedia v0.0.5 is alpha with ~13 weekly downloads. Data freshness depends on npm releases. Mitigation: frontend still shows "Fetch from API" button for on-demand provider querying.
- modelpedia covers 22/29 CocoCat providers. Uncovered providers keep existing backend-driven flow.
- Anthropic `chat_stream()` not implemented, so no streaming token usage yet. Only affects Anthropic.
