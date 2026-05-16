# Model Catalog & Token Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate modelpedia as the authoritative model catalog in the frontend, and add structured token usage logging to all LLM provider backends.

**Architecture:** Frontend reads model lists from modelpedia (4263 models, 30+ providers) as primary data source, falling back to backend `fetch-models` for uncovered providers. Backend provider classes extract `usage` from API responses and emit structured JSON logs via `cococat/providers/usage.py`.

**Tech Stack:** TypeScript/React (web-ui), Python/FastAPI/httpx (backend), modelpedia npm package

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `web-ui/package.json` | Modify | Add `modelpedia` dependency |
| `web-ui/src/lib/model-catalog.ts` | Create | Provider mapping + model query functions |
| `web-ui/src/components/settings/ProvidersTab.tsx` | Modify | Use modelpedia for available models, add metadata display |
| `cococat/routes/providers.py` | Modify | Simplify `GET /providers/{name}/models` — remove `available` |
| `cococat/providers/usage.py` | Create | `TokenUsage` dataclass + `log_usage()` |
| `cococat/providers/openai_compat.py` | Modify | Extract & log usage in `chat()` and `chat_stream()` |
| `cococat/providers/anthropic.py` | Modify | Extract & log usage in `chat()` |

---

### Task 1: Install modelpedia dependency

**Files:**
- Modify: `web-ui/package.json`

- [ ] **Step 1: Install modelpedia**

```bash
cd web-ui && npm install modelpedia
```

- [ ] **Step 2: Verify installation**

```bash
ls node_modules/modelpedia/dist/
```

Expected: `index.mjs`, `index.cjs`, `index.d.mts`, types files, `providers/` directory exist.

---

### Task 2: Create model catalog mapping layer

**Files:**
- Create: `web-ui/src/lib/model-catalog.ts`

- [ ] **Step 1: Write `model-catalog.ts`**

```typescript
import {
  getModelsByProvider,
  getModel,
  providers,
  type Model,
} from "modelpedia"

// Map CocoCat internal provider names → modelpedia provider IDs
const PROVIDER_MAP: Record<string, string> = {
  openai: "openai",
  anthropic: "anthropic",
  deepseek: "deepseek",
  gemini: "google",
  dashscope: "alibaba",
  moonshot: "moonshot",
  minimax: "minimax",
  mistral: "mistral",
  groq: "groq",
  xai: "xai",
  together: "together",
  fireworks: "fireworks",
  deepinfra: "deepinfra",
  cerebras: "cerebras",
  openrouter: "openrouter",
  cohere: "cohere",
  perplexity: "perplexity",
  replicate: "replicate",
  huggingface: "huggingface",
  ollama: "ollama",
  azure: "azure",
  "aws-bedrock": "amazon",
}

// All modelpedia provider IDs for fast lookup
const MODELPEDIA_IDS = new Set(providers.map((p) => p.id))

/**
 * Check if modelpedia covers a given CocoCat provider.
 */
export function isProviderSupported(cocoName: string): boolean {
  const mpId = PROVIDER_MAP[cocoName]
  if (mpId) return true
  // Direct match (e.g. "openai" already matches)
  return MODELPEDIA_IDS.has(cocoName)
}

/**
 * Get all non-deprecated models for a CocoCat provider from modelpedia.
 * Sorted: active → preview → undefined status.
 * Returns empty array if provider not covered.
 */
export function getCatalogModels(cocoName: string): Model[] {
  const mpId = PROVIDER_MAP[cocoName] || cocoName
  const all = getModelsByProvider(mpId)
  if (!all || all.length === 0) return []

  const filtered = all.filter((m) => m.status !== "deprecated")
  const order: Record<string, number> = { active: 0, preview: 1 }
  filtered.sort((a, b) => {
    const oa = order[a.status || ""] ?? 2
    const ob = order[b.status || ""] ?? 2
    return oa - ob
  })
  return filtered
}

/**
 * Get full metadata for a single model.
 */
export function getCatalogMeta(
  cocoName: string,
  modelId: string,
): Model | undefined {
  const mpId = PROVIDER_MAP[cocoName] || cocoName
  return getModel(mpId, modelId)
}

/**
 * Get provider metadata from modelpedia (api_url, docs_url, etc.).
 */
export function getCatalogProvider(cocoName: string) {
  const mpId = PROVIDER_MAP[cocoName] || cocoName
  const { getProvider } = require("modelpedia")
  return getProvider(mpId)
}
```

- [ ] **Step 2: Run TypeScript typecheck**

```bash
cd web-ui && npx tsc --noEmit src/lib/model-catalog.ts
```

Expected: No errors.

---

### Task 3: Update ProviderDetailPanel to use modelpedia catalog

**Files:**
- Modify: `web-ui/src/components/settings/ProvidersTab.tsx:1-493`

- [ ] **Step 1: Add imports**

Replace the existing imports block (lines 1-4) with:

```typescript
import { useState, useEffect, useRef, useMemo } from "react"
import { Loader2, Plus, Trash2, Eye, EyeOff, CheckCircle2, XCircle, ChevronsRight, ChevronRight, ChevronLeft, ChevronsLeft, Search, Info } from "lucide-react"
import { PROVIDER_ICONS } from "@/lib/provider-icons"
import { getCatalogModels, getCatalogMeta, isProviderSupported } from "@/lib/model-catalog"
import type { ProviderInfo, TabData } from "@/types/settings"
import type { Model } from "modelpedia"
```

- [ ] **Step 2: Add ModelMetaTooltip component**

Add before `ProviderDetailPanel` (after line 131):

```typescript
function ModelMetaTooltip({ model }: { model: Model }) {
  const lines: string[] = []
  if (model.context_window) lines.push(`上下文: ${(model.context_window / 1000).toFixed(0)}k tokens`)
  if (model.max_output_tokens) lines.push(`最大输出: ${(model.max_output_tokens / 1000).toFixed(0)}k tokens`)
  if (model.pricing) {
    const cost = `$${model.pricing.input}/$${model.pricing.output} (每百万 token)`
    lines.push(`定价: ${cost}`)
  }
  if (model.status) lines.push(`状态: ${model.status}`)
  if (!lines.length) return null
  return (
    <div className="invisible group-hover:visible absolute bottom-full left-0 mb-1 z-50 w-56 bg-slate-800 text-slate-100 text-[10px] rounded-lg px-3 py-2 shadow-lg leading-relaxed">
      {lines.map((l, i) => <div key={i}>{l}</div>)}
    </div>
  )
}
```

- [ ] **Step 3: Replace model loading useEffect**

Replace the existing model-loading `useEffect` (lines 161-169) with:

```typescript
// Build available models: modelpedia catalog merged with API-discovered models
const catalogModels = useMemo(() => {
  if (!provider) return []
  return getCatalogModels(providerName)
}, [providerName, provider?.name])

// Merge catalog + API-discovered, deduped
const mergedAvailable = useMemo(() => {
  const catalogIds = new Set(catalogModels.map((m) => m.id))
  const merged = [...catalogModels.map((m) => m.id)]
  for (const m of (discoveredModels || [])) {
    if (!catalogIds.has(m)) merged.push(m)
  }
  // If modelpedia doesn't cover this provider, use backend available
  if (catalogModels.length === 0) {
    return [...new Set([...merged, ...models.available])].filter(
      (id) => !models.enabled.includes(id),
    )
  }
  return merged.filter((id) => !models.enabled.includes(id))
}, [catalogModels, discoveredModels, models.available, models.enabled])

// Load enabled models from backend
useEffect(() => {
  fetch(`/api/providers/${encodeURIComponent(providerName)}/models`)
    .then((r) => r.json())
    .then((d) => {
      if (d.enabled) {
        setModels((prev) => ({
          ...prev,
          enabled: d.enabled || [],
          default: d.default || "",
        }))
      }
      setModelsLoaded(true)
    })
    .catch(() => setModelsLoaded(true))
}, [providerName])
```

- [ ] **Step 4: Replace availModels computation**

Replace line 171 `const availModels = ...` with:

```typescript
const availModels = mergedAvailable
```

- [ ] **Step 5: Add search state and filtered available list**

Add state after `const [dragId, setDragId] = useState<string | null>(null)` (after line 153):

```typescript
const [modelSearch, setModelSearch] = useState("")
```

Replace the `availModels` declaration (the one we just replaced) with:

```typescript
const availModels = mergedAvailable.filter((m) =>
  !modelSearch || m.toLowerCase().includes(modelSearch.toLowerCase()),
)
```

- [ ] **Step 6: Add ModelMetaTooltip to available model items**

Replace the available model item template (lines 389-408) — add `group relative` and `ModelMetaTooltip`:

```typescript
{availModels.map(m => {
  const meta = getCatalogMeta(providerName, m)
  return (
    <div
      key={m}
      draggable
      onDragStart={e => onDragStart(e, m)}
      onDragEnd={onDragEnd}
      className={`group relative flex items-center gap-2 px-2 py-1.5 rounded hover:bg-background cursor-pointer text-xs mb-0.5 transition-colors ${dragId === m ? "opacity-40" : ""}`}
    >
      <input
        type="checkbox"
        checked={checkedAvailable.has(m)}
        onChange={() => {
          const next = new Set(checkedAvailable)
          next.has(m) ? next.delete(m) : next.add(m)
          setCheckedAvailable(next)
        }}
        className="rounded border-slate-300 shrink-0"
      />
      <span className="text-slate-700 truncate flex-1">{m}</span>
      {meta?.status === "deprecated" && (
        <span className="text-[9px] px-1 py-0 rounded bg-amber-100 text-amber-600 shrink-0">旧</span>
      )}
      {meta?.status === "active" && (
        <span className="text-[9px] px-1 py-0 rounded bg-green-100 text-green-600 shrink-0">新</span>
      )}
      {meta && <ModelMetaTooltip model={meta} />}
    </div>
  )
})}
```

- [ ] **Step 7: Add search input above available models column**

Replace the available column header (lines 387-388) — add search input:

```typescript
<div className="px-3 py-1.5 text-[10px] text-muted-foreground uppercase font-medium border-b border-border/30 shrink-0 space-y-1">
  <div>可用模型</div>
  <div className="relative">
    <Search className="size-3 absolute left-1.5 top-1/2 -translate-y-1/2 text-slate-300" />
    <input
      value={modelSearch}
      onChange={e => setModelSearch(e.target.value)}
      placeholder="筛选..."
      className="w-full rounded border border-border/50 bg-white pl-5 pr-2 py-0.5 text-[10px] font-normal normal-case focus:outline-none focus:ring-1 focus:ring-blue-400/30"
    />
  </div>
</div>
```

- [ ] **Step 8: Run TypeScript typecheck**

```bash
cd web-ui && npx tsc --noEmit
```

Expected: No errors (may have pre-existing errors unrelated to this change).

---

### Task 4: Simplify backend GET /providers/{name}/models

**Files:**
- Modify: `cococat/routes/providers.py:438-468`

- [ ] **Step 1: Update `get_provider_models` to remove `available` field**

Replace the function body (lines 438-468) with:

```python
@router.get("/providers/{name}/models")
async def get_provider_models(name: str):
    """Get structured models for a provider.

    Returns {enabled: [...], default: "..."}.
    enabled = user-saved enabled models.
    Available models are now provided by the frontend via modelpedia catalog.
    """
    reg = create_builtin_registry()
    spec = reg.find_by_name(name)
    custom_prov = None if spec else _find_custom_provider(name)

    if not spec and not custom_prov:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")

    user_models = _load_user_models()
    enabled = list(user_models.get(name, []))
    defaults = _load_default_models()

    default = defaults.get(name, enabled[0] if enabled else "")

    return {
        "enabled": enabled,
        "default": default,
    }
```

- [ ] **Step 2: Remove unused `_MODELS_CACHE` reference**

In `get_provider_models`, the `_MODELS_CACHE` import/usage for `available` is gone. The cache is still used in `fetch_provider_models` (line 430), so keep the module-level variable. No changes needed elsewhere.

- [ ] **Step 3: Verify backend starts without errors**

```bash
cd /home/leaif/Project/CocoCat && python -c "from cococat.routes.providers import router; print('OK')"
```

Expected: `OK` (no import errors).

---

### Task 5: Create token usage logging module

**Files:**
- Create: `cococat/providers/usage.py`

- [ ] **Step 1: Write `usage.py`**

```python
"""Structured token usage logging for LLM providers."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger("cococat.providers.usage")


@dataclass
class TokenUsage:
    """Token consumption for a single LLM API call."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    provider: str
    duration_ms: float


def log_usage(usage: TokenUsage) -> None:
    """Emit structured token usage as a JSON log line."""
    logger.info(json.dumps(asdict(usage), ensure_ascii=False))
```

- [ ] **Step 2: Verify module imports cleanly**

```bash
cd /home/leaif/Project/CocoCat && python -c "from cococat.providers.usage import TokenUsage, log_usage; print('OK')"
```

Expected: `OK`.

---

### Task 6: Instrument OpenAICompatProvider with usage logging

**Files:**
- Modify: `cococat/providers/openai_compat.py:1-192`

- [ ] **Step 1: Add imports**

Replace the import block (lines 3-13) with:

```python
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

import httpx

from cococat.providers.base import BaseProvider, LLMResponse, ToolCallRequest
from cococat.providers.usage import TokenUsage, log_usage

logger = logging.getLogger("cococat.providers.openai_compat")
```

- [ ] **Step 2: Add `_log_usage` helper method**

Insert after `_build_request` (after line 80), before `chat()`:

```python
    def _log_usage(self, data: dict, start_time: float, provider_name: str = "") -> None:
        """Extract usage from API response and log it."""
        usage = data.get("usage", {})
        if not usage:
            return
        elapsed_ms = (time.monotonic() - start_time) * 1000
        log_usage(TokenUsage(
            model=data.get("model", self._model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            provider=provider_name,
            duration_ms=round(elapsed_ms, 1),
        ))
```

- [ ] **Step 3: Instrument `chat()` method**

Replace the `chat()` method body (lines 82-123). Add `start_time` and call `_log_usage` before return:

```python
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Send a non-streaming chat request."""
        body = self._build_request(messages, tools, stream=False)
        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        msg = choice["message"]
        content = msg.get("content") or ""
        tool_calls = [
            ToolCallRequest(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=tc["function"]["arguments"],
            )
            for tc in (msg.get("tool_calls") or [])
        ]
        finish_reason = choice.get("finish_reason", "stop")
        usage = data.get("usage", {})

        self._log_usage(data, start_time)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)},
            reasoning_content=msg.get("reasoning_content"),
        )
```

- [ ] **Step 4: Instrument `chat_stream()` method**

Replace the `chat_stream()` method body (lines 125-192). Add `start_time` and capture final usage chunk:

```python
    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """Send a streaming chat request. Yields {'type': 'delta'|'tool_call'|'reasoning'|'done', ...}."""
        body = self._build_request(messages, tools, stream=True)
        body["stream_options"] = {"include_usage": True}
        start_time = time.monotonic()

        accumulated = []
        tc_buffer: dict[int, dict] = {}  # index → {id, name, arguments}
        last_usage: dict = {}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            # Capture usage from final chunk (OpenAI sends usage in last chunk with stream_options)
                            if "usage" in chunk:
                                last_usage = chunk
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            reasoning = delta.get("reasoning_content", "")
                            tool_calls = delta.get("tool_calls")

                            if content:
                                accumulated.append(content)
                                yield {"type": "delta", "content": content}
                            if reasoning:
                                yield {"type": "reasoning", "content": reasoning}
                            if tool_calls:
                                for tc in tool_calls:
                                    idx = tc.get("index", 0)
                                    if idx not in tc_buffer:
                                        tc_buffer[idx] = {"id": "", "name": "", "arguments": ""}
                                    entry = tc_buffer[idx]
                                    if "id" in tc and tc["id"]:
                                        entry["id"] = tc["id"]
                                    func = tc.get("function", {})
                                    if func.get("name"):
                                        entry["name"] = func["name"]
                                    if func.get("arguments"):
                                        entry["arguments"] += func["arguments"]
                                    if entry["name"] and entry["arguments"]:
                                        try:
                                            json.loads(entry["arguments"])
                                            yield {"type": "tool_call", "id": entry["id"], "name": entry["name"], "arguments": entry["arguments"]}
                                            tc_buffer[idx] = {"id": "", "name": "", "arguments": ""}
                                        except json.JSONDecodeError:
                                            pass
                        except json.JSONDecodeError:
                            continue

        self._log_usage(last_usage, start_time)
        yield {"type": "done", "content": "".join(accumulated)}
```

- [ ] **Step 5: Pass provider name to `_log_usage`**

The `_log_usage` call in `chat()` and `chat_stream()` needs the provider name. Store it in `__init__`:

Replace the `__init__` method (lines 49-59) with:

```python
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        provider_name: str = "",
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._provider_name = provider_name
```

Then update the `_log_usage` calls in `chat()` and `chat_stream()` to pass `provider_name=self._provider_name` instead of the empty string.

Wait — let me update the plan properly. The `_log_usage` call in `chat()` at the point we added it should be:

```python
        self._log_usage(data, start_time, provider_name=self._provider_name)
```

And in `chat_stream()`:

```python
        self._log_usage(last_usage, start_time, provider_name=self._provider_name)
```

- [ ] **Step 6: Update factory to pass provider name**

In `cococat/providers/factory.py:60-64`, update the `_build_provider` method to pass `provider_name`:

```python
        return OpenAICompatProvider(
            api_key=api_key,
            base_url=base_url,
            model=effective_model,
            provider_name=spec.name,
        )
```

- [ ] **Step 7: Verify Python module imports**

```bash
cd /home/leaif/Project/CocoCat && python -c "from cococat.providers.openai_compat import OpenAICompatProvider; print('OK')"
```

Expected: `OK`.

---

### Task 7: Instrument AnthropicProvider with usage logging

**Files:**
- Modify: `cococat/providers/anthropic.py:1-174`

- [ ] **Step 1: Add imports**

Replace imports (lines 3-13) with:

```python
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

import httpx

from cococat.providers.base import BaseProvider, LLMResponse, ToolCallRequest
from cococat.providers.usage import TokenUsage, log_usage

logger = logging.getLogger("cococat.providers.anthropic")
```

- [ ] **Step 2: Add `_log_usage` helper method**

Insert after `_build_request` (after line 113), before `chat()`:

```python
    def _log_usage(self, data: dict, start_time: float) -> None:
        """Extract usage from Anthropic response and log it."""
        usage = data.get("usage", {})
        if not usage:
            return
        elapsed_ms = (time.monotonic() - start_time) * 1000
        log_usage(TokenUsage(
            model=data.get("model", self._model),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            provider="anthropic",
            duration_ms=round(elapsed_ms, 1),
        ))
```

- [ ] **Step 3: Instrument `chat()` method**

Replace the `chat()` method body (lines 115-163). Add `start_time` and call `_log_usage`:

```python
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> LLMResponse:
        system, converted = self._convert_messages(messages)
        body = self._build_request(converted, system=system, tools=tools)
        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        content = ""
        tool_calls: list[ToolCallRequest] = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(ToolCallRequest(
                    id=block["id"],
                    name=block["name"],
                    arguments=block["input"],
                ))

        stop_reason = data.get("stop_reason", "end_turn")
        finish = "stop"
        if stop_reason == "tool_use":
            finish = "tool_calls"
        elif stop_reason == "max_tokens":
            finish = "length"

        usage = data.get("usage", {})

        self._log_usage(data, start_time)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage={"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)},
        )
```

- [ ] **Step 4: Verify Python module imports**

```bash
cd /home/leaif/Project/CocoCat && python -c "from cococat.providers.anthropic import AnthropicProvider; print('OK')"
```

Expected: `OK`.

---

### Task 8: Final verification

- [ ] **Step 1: Run Python import check for all changed modules**

```bash
cd /home/leaif/Project/CocoCat && python -c "
from cococat.providers.usage import TokenUsage, log_usage
from cococat.providers.openai_compat import OpenAICompatProvider
from cococat.providers.anthropic import AnthropicProvider
from cococat.routes.providers import router
print('All imports OK')
"
```

- [ ] **Step 2: Run frontend TypeScript typecheck**

```bash
cd web-ui && npx tsc --noEmit 2>&1 | head -30
```

Expected: Only pre-existing errors (if any), no new errors from modelpedia/model-catalog imports.

- [ ] **Step 3: Quick smoke test — verify modelpedia data is accessible**

```bash
cd web-ui && node -e "
const { getModelsByProvider } = require('./node_modules/modelpedia/dist/index.cjs');
console.log('DeepSeek models:', getModelsByProvider('deepseek').length);
console.log('OpenAI models:', getModelsByProvider('openai').length);
console.log('Anthropic models:', getModelsByProvider('anthropic').length);
"
```

Expected: Non-zero counts printed.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: modelpedia catalog integration and token usage logging

Frontend: Use modelpedia as authoritative model catalog in ProviderDetailPanel,
with metadata display (context window, pricing, status badges) and search filter.

Backend: Add structured TokenUsage logging in OpenAICompatProvider and
AnthropicProvider via cococat/providers/usage.py. Simplify GET /providers/{name}/models
to only return enabled/default (available now comes from modelpedia)."
```
