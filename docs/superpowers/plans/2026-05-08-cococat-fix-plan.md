# CocoCat 核心问题修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Hire 页面、Usage 页面、LLM Provider 配置、Chat 错误提示 4 个核心问题

**Architecture:** 分 4 个独立 Phase 按依赖顺序实施：Provider 修复 → Chat 错误提示 → Usage 数据修复 → Hire AI 招聘流程。每个 Phase 可独立验证。

**Tech Stack:** Rust (Axum), Python (FastAPI), React (TypeScript), SQLite

---

## 文件结构

### Phase 1: LLM Provider Fix
| 操作 | 文件 |
|------|------|
| 修改 | `py-agent/providers/factory.py` |
| 修改 | `web/routes/providers.py` |

### Phase 2: Chat Error Handling
| 操作 | 文件 |
|------|------|
| 修改 | `web-ui/src/pages/Chat.tsx` |

### Phase 3: Usage Data Fix
| 操作 | 文件 |
|------|------|
| 修改 | `py-agent/agent_loop.py` |
| 修改 | `web-ui/src/pages/TokenUsage.tsx` |
| 修改 | `src/db/usage.rs` |

### Phase 4: Hire AI Flow
| 操作 | 文件 |
|------|------|
| 修改 | `src/api/router.rs` |
| 修改 | `src/api/hire.rs` |
| 修改 | `src/db/hire.rs` |
| 修改 | `web-ui/src/pages/Hiring.tsx` |
| 修改 | `web-ui/src/api/hiring.ts` |

---

## Phase 1: LLM Provider 系统修复

### Task 1.1: 修复 `make_provider()` 的 auth.json 支持

**Files:**
- Modify: `py-agent/providers/factory.py`

- [ ] **Step 1: 在 factory.py 中添加 `make_provider_by_name()` 函数**

```python
def make_provider_by_name(name: str) -> LLMProvider | None:
    """Create a provider by registry name (not model name).
    
    Bypasses model-name-based matching and directly looks up the provider spec.
    Respects auth.json, env vars, and config/providers.json in that priority.
    """
    from .registry import PROVIDERS
    spec = next((p for p in PROVIDERS if p.name == name), None)
    if not spec:
        return None

    from provider_config import get_provider as _get_provider_cfg, get_api_key

    api_key = get_api_key(spec.name) or _get_env(spec) or os.environ.get("OPENAI_API_KEY", "")
    cfg = _get_provider_cfg(spec.name)
    base_url = cfg.get("api_base", "") or spec.default_api_base
    
    # Use configured default_model or registry default
    model = cfg.get("default_model", "") or os.environ.get("LLM_MODEL", "gpt-4o-mini")

    if spec.backend == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model, base_url=base_url)

    from .openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(api_key=api_key, model=model, base_url=base_url)
```

- [ ] **Step 2: 在 `make_provider()` 中 fallback 时增加 auth.json 检查**

```python
def _find_first_available() -> ProviderSpec | None:
    from .registry import PROVIDERS
    for spec in PROVIDERS:
        # Check env var first, then auth.json
        if _get_env(spec):
            return spec
        from provider_config import get_api_key
        if get_api_key(spec.name):
            return spec
    return None
```

- [ ] **Step 3: 运行测试验证**

Run: `cd /home/leaif/CocoCat && python -c "from py-agent.providers.factory import make_provider_by_name; p = make_provider_by_name('deepseek'); print(f'Provider created: {p.__class__.__name__}, key set: {bool(p.api_key)}')"`

Expected: Provider created successfully with api_key from auth.json

- [ ] **Step 4: Commit**

```bash
git add py-agent/providers/factory.py
git commit -m "fix: support auth.json API keys in make_provider"
```

### Task 1.2: 修复 Test 端点

**Files:**
- Modify: `web/routes/providers.py:103-130`

- [ ] **Step 1: 修改 `test_provider()` 使用 `make_provider_by_name()`**

```python
@router.post("/api/providers/{name}/test")
def test_provider(name: str):
    """Test provider connectivity by listing models."""
    from providers.registry import PROVIDERS
    from providers.factory import make_provider_by_name

    spec = next((p for p in PROVIDERS if p.name == name), None)
    if not spec:
        return JSONResponse({"error": f"provider '{name}' not found"}, status_code=404)

    if not spec.default_api_base:
        return {"status": "error", "message": "provider has no default API base URL"}

    try:
        provider = make_provider_by_name(name)
        if provider is None:
            return {"status": "error", "message": "provider creation failed"}
        if not provider.api_key:
            return {"status": "error", "message": "no API key configured"}

        import httpx
        api_base = provider.api_base.rstrip("/")
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        resp = httpx.get(f"{api_base}/v1/models", headers=headers, timeout=10)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            model_names = [m.get("id", "") for m in models[:10]]
            return {"status": "ok", "models": model_names}
        else:
            return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 2: 手动测试**

Run `curl -X POST http://localhost:8080/api/providers/deepseek/test -H "Authorization: Bearer $(cat /path/to/token)" -H "Content-Type: application/json" -d '{}'`

Expected: `{"status": "ok", "models": ["deepseek-chat", ...]}`

- [ ] **Step 3: Commit**

```bash
git add web/routes/providers.py
git commit -m "fix: use make_provider_by_name in test endpoint"
```

---

## Phase 2: Chat 页面分层错误提示

### Task 2.1: 添加 provider 配置检查 + 发送失败错误提示

**Files:**
- Modify: `web-ui/src/pages/Chat.tsx`

- [ ] **Step 1: 添加 provider 健康状态查询，发送按钮条件禁用**

```typescript
// 在 Chat 组件内，现有 query hooks 之后添加
const { data: providersData } = useQuery({
  queryKey: ["providers"],
  queryFn: () => providersApi.list(),
})

const hasConfiguredProvider = (providersData?.providers ?? []).some(p => p.has_key)
```

- [ ] **Step 2: 添加导入语句**

```typescript
// 在文件顶部的现有 import 之后添加
import { providersApi } from "@/api/providers"
// useMemo 用于缓存失败消息列表
import { useState, useEffect, useCallback, useRef, useMemo } from "react"
```

- [ ] **Step 3: 在输入区域添加 provider 未配置提示条**

```tsx
{/* Provider 配置提示 - 在输入框上方 */}
{!hasConfiguredProvider && (
  <div className="px-4 py-2 bg-amber-50 dark:bg-amber-950 border-t border-amber-200 dark:border-amber-800">
    <p className="text-xs text-amber-700 dark:text-amber-300 flex items-center gap-1">
      <span>⚠️</span>
      <span>
        API Key 未配置，请前往{" "}
        <a href="/settings" className="underline font-medium">设置页面</a>
        {" "}配置后再试
      </span>
    </p>
  </div>
)}
```

- [ ] **Step 4: 禁用发送按钮当 provider 未配置**

```tsx
{/* 修改发送按钮，添加禁用条件 */}
<Button onClick={sendMessage}
  disabled={!message.trim() || !hasConfiguredProvider}
  className="shrink-0 self-end">
  <Send className="size-4" />
</Button>
```

- [ ] **Step 5: 在 `sendMessage()` catch 块中添加 toast 错误提示**

```typescript
try {
  await chatApi.sendMessage(selectedGroup, content)
} catch (e) {
  setLocalStreaming(false)
  if (localStreamTimer.current) clearTimeout(localStreamTimer.current)
  queryClient.setQueryData(["chat-messages", selectedGroup], prev)
  const msg = e instanceof Error ? e.message : "发送失败"
  toast.error(`❌ ${msg}`, {
    description: !hasConfiguredProvider ? "请先配置 API Key" : undefined,
    action: !hasConfiguredProvider ? {
      label: "去设置",
      onClick: () => window.location.href = "/settings",
    } : undefined,
  })
  return
}
```

- [ ] **Step 6: 监听 streamState 中的 failed 事件，在消息列表中显示错误**

```tsx
// 在 return 之前，messages 渲染部分之前，添加错误消息处理
const failedMessages = useMemo(() => {
  const failed: { id: number; content: string; timestamp: string }[] = []
  for (const s of streamState.values()) {
    if (s.status === "failed" && s.task_uuid) {
      failed.push({
        id: -Date.now() - Math.random(),
        content: `❌ Agent 回复失败: ${s.error || "请检查 API Key 配置"}`,
        timestamp: new Date(s.updatedAt).toISOString(),
      })
    }
  }
  return failed
}, [renderTick])
```

- [ ] **Step 7: 在消息列表中渲染失败消息（插入错误的 filter 逻辑前）**

```tsx
{/* 在 messages.filter(...) 之后，MessageBubble 渲染之前 */}
{failedMessages.map(fm => (
  <div key={fm.id} className="flex justify-center py-2">
    <span className="text-xs text-red-500 bg-red-50 dark:bg-red-950/50 rounded px-3 py-1.5">
      {fm.content}
    </span>
  </div>
))}
```

- [ ] **Step 8: Commit**

```bash
git add web-ui/src/pages/Chat.tsx
git commit -m "feat: add layered error hints to Chat page"
```

---

## Phase 3: Usage 数据修复

### Task 3.1: 修复 agent_loop.py 中的 usage 字段名

**Files:**
- Modify: `py-agent/agent_loop.py:370-371`

- [ ] **Step 1: 修改 usage 字段名映射**

```python
# 修改前 (agent_loop.py:370-371):
total_usage["input"] += u.get("input_tokens", 0) or 0
total_usage["output"] += u.get("output_tokens", 0) or 0

# 修改后:
total_usage["input"] += u.get("prompt_tokens", 0) or u.get("input_tokens", 0) or 0
total_usage["output"] += u.get("completion_tokens", 0) or u.get("output_tokens", 0) or 0
```

- [ ] **Step 2: 验证修复**

Run: `cd /home/leaif/CocoCat && python -c "
import json, os
from py-agent.agent_loop import _log_usage
# Simulate a usage dict from OpenAI API
usage = {'input': 100, 'output': 50}
_log_usage('test_agent', 'test prompt', usage, 1)
path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath('py-agent/agent_loop.py'))), 'agents', '_usage.jsonl')
if os.path.exists(path):
    with open(path) as f:
        print('Usage logged:', f.read())
    os.remove(path)
else:
    print('File not created - bug still exists')
"`

Expected: "Usage logged: {"timestamp": "...", "agent_id": "test_agent", ...}

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "fix: map OpenAI prompt_tokens/completion_tokens in usage logging"
```

### Task 3.2: 改善 Usage 空状态显示

**Files:**
- Modify: `web-ui/src/pages/TokenUsage.tsx`

- [ ] **Step 1: 修改空状态提示**

```tsx
{!isLoading && usage.length === 0 && (
  <div className="text-center py-10 text-muted-foreground">
    <Cpu className="size-12 mx-auto mb-4 opacity-30" />
    <p>{t("usage.no_data")}</p>
    <p className="text-sm mt-2">
      尚未产生用量数据。请先在 Chat 页面与 agent 对话，用量数据将自动记录。
    </p>
    <Button variant="outline" size="sm" className="mt-4" onClick={() => window.location.href = "/chat"}>
      前往 Chat
    </Button>
  </div>
)}
```

- [ ] **Step 2: 修复加载状态渲染顺序**

```tsx
// 修改渲染逻辑，确保加载中、错误、空数据按正确顺序处理
if (isLoading) return <TableSkeleton rows={5} cols={6} />
if (isError) return <ErrorState message={error?.message} onRetry={refetch} />
```

Need to add Button import:
```typescript
// 添加 Button 导入（现有 TokenUsage.tsx 中未导入 Button）
import { Button } from "@/components/ui/button"
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/TokenUsage.tsx
git commit -m "feat: improve usage page empty state with guidance"
```

### Task 3.3: 支持 COCOCAT_WORKSPACE 路径覆盖

**Files:**
- Modify: `src/db/usage.rs`

- [ ] **Step 1: 修改 `get_usage_log_path()` 支持运行时路径**

```rust
pub fn get_usage_log_path() -> PathBuf {
    // Support COCOCAT_WORKSPACE env var override
    if let Ok(workspace) = std::env::var("COCOCAT_WORKSPACE") {
        if !workspace.is_empty() {
            let mut p = PathBuf::from(workspace);
            p.push("agents");
            p.push("_usage.jsonl");
            return p;
        }
    }
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.push("agents");
    p.push("_usage.jsonl");
    p
}
```

- [ ] **Step 2: Commit**

```bash
git add src/db/usage.rs
git commit -m "feat: support COCOCAT_WORKSPACE for usage log path"
```

---

## Phase 4: Hire AI 招聘流程

### Task 4.1: 添加 hire_plans 和 hire_candidates 数据库表

**Files:**
- Modify: `src/db/hire.rs`

- [ ] **Step 1: 添加表结构和 CRUD 函数**

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HirePlan {
    pub id: i64,
    pub plan_uuid: String,
    pub position: String,
    pub skills: String,
    pub responsibilities: String,
    pub traits: String,
    pub requested_count: i64,
    pub status: String,  // generating, completed, failed
    pub created_at: String,
    pub completed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HireCandidate {
    pub id: i64,
    pub candidate_uuid: String,
    pub plan_uuid: String,
    pub name: String,
    pub profile: String,  // JSON string
    pub status: String,   // pending, approved, rejected
    pub created_at: String,
    pub decided_at: Option<String>,
    pub reviewer: Option<String>,
}

pub fn create_plan(
    pool: &DbPool,
    plan_uuid: &str,
    position: &str,
    skills: &str,
    responsibilities: &str,
    traits: &str,
    count: i64,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO hire_plans (plan_uuid, position, skills, responsibilities, traits, requested_count, status)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'generating')",
        params![plan_uuid, position, skills, responsibilities, traits, count],
    )?;
    Ok(())
}

pub fn insert_candidate(
    pool: &DbPool,
    candidate_uuid: &str,
    plan_uuid: &str,
    name: &str,
    profile: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO hire_candidates (candidate_uuid, plan_uuid, name, profile, status)
         VALUES (?1, ?2, ?3, ?4, 'pending')",
        params![candidate_uuid, plan_uuid, name, profile],
    )?;
    Ok(())
}

pub fn list_pending_candidates(pool: &DbPool) -> Result<Vec<HireCandidate>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, candidate_uuid, plan_uuid, name, profile, status, created_at, decided_at, reviewer
         FROM hire_candidates WHERE status = 'pending'
         ORDER BY created_at ASC"
    )?;
    let candidates = stmt.query_map([], |row| {
        Ok(HireCandidate {
            id: row.get(0)?,
            candidate_uuid: row.get(1)?,
            plan_uuid: row.get(2)?,
            name: row.get(3)?,
            profile: row.get(4)?,
            status: row.get(5)?,
            created_at: row.get(6)?,
            decided_at: row.get(7)?,
            reviewer: row.get(8)?,
        })
    })?
    .filter_map(|r| r.ok())
    .collect();
    Ok(candidates)
}

pub fn approve_candidate(
    pool: &DbPool,
    candidate_uuid: &str,
    reviewer: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE hire_candidates SET status = 'approved', reviewer = ?1, decided_at = datetime('now')
         WHERE candidate_uuid = ?2",
        params![reviewer, candidate_uuid],
    )?;
    Ok(())
}

pub fn reject_candidate(
    pool: &DbPool,
    candidate_uuid: &str,
    reviewer: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE hire_candidates SET status = 'rejected', reviewer = ?1, decided_at = datetime('now')
         WHERE candidate_uuid = ?2",
        params![reviewer, candidate_uuid],
    )?;
    Ok(())
}
```

- [ ] **Step 2: 添加数据库迁移（在 `db/pool.rs` 中的 `run_migrations` 函数内）**

在 `src/db/pool.rs` 中的 `run_migrations` 函数末尾添加：

```rust
conn.execute_batch(
    "CREATE TABLE IF NOT EXISTS hire_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_uuid TEXT NOT NULL UNIQUE,
        position TEXT NOT NULL,
        skills TEXT DEFAULT '',
        responsibilities TEXT DEFAULT '',
        traits TEXT DEFAULT '',
        requested_count INTEGER DEFAULT 5,
        status TEXT DEFAULT 'generating',
        created_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS hire_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_uuid TEXT NOT NULL UNIQUE,
        plan_uuid TEXT NOT NULL,
        name TEXT NOT NULL,
        profile TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now')),
        decided_at TEXT,
        reviewer TEXT,
        FOREIGN KEY (plan_uuid) REFERENCES hire_plans(plan_uuid)
    );"
)?;
```

- [ ] **Step 3: Commit**

```bash
git add src/db/hire.rs src/db/pool.rs
git commit -m "feat: add hire_plans and hire_candidates tables"
```

### Task 4.2: 添加 Hire API 端点

**Files:**
- Modify: `src/api/hire.rs`
- Modify: `src/api/router.rs`

- [ ] **Step 1: 在 `src/api/hire.rs` 中添加 `plan_handler` 和 `list_candidates_handler`**

添加到 `src/api/hire.rs` 文件末尾：

```rust
#[derive(Deserialize)]
pub struct PlanRequest {
    pub position: String,
    pub skills: Option<String>,
    pub responsibilities: Option<String>,
    pub traits: Option<String>,
    pub count: Option<i64>,
}

#[derive(Serialize)]
pub struct PlanResponse {
    pub plan_uuid: String,
    pub status: String,
}

pub async fn plan_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<PlanRequest>,
) -> Result<Json<PlanResponse>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    
    let plan_uuid = uuid::Uuid::new_v4().to_string();
    let position = req.position.trim().to_string();
    if position.is_empty() {
        return Err(StatusCode::BAD_REQUEST);
    }
    
    hire::create_plan(
        &state.db_pool,
        &plan_uuid,
        &position,
        &req.skills.unwrap_or_default(),
        &req.responsibilities.unwrap_or_default(),
        &req.traits.unwrap_or_default(),
        req.count.unwrap_or(5),
    ).map_err(|e| {
        tracing::error!("Failed to create hire plan: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    
    // Dispatch task to leader agent
    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "plan_uuid": plan_uuid,
        "position": position,
        "skills": req.skills.unwrap_or_default(),
        "responsibilities": req.responsibilities.unwrap_or_default(),
        "traits": req.traits.unwrap_or_default(),
        "count": req.count.unwrap_or(5),
    });
    
    tasks::create_task(
        &state.db_pool,
        &NewTask {
            task_uuid: task_uuid.clone(),
            target_agent: "leader".to_string(),
            source: "web".into(),
            method: "hire_plan".into(),
            params: params.to_string(),
        },
    ).map_err(|e| {
        tracing::error!("Failed to create hire task: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    
    state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await.map_err(|e| {
        tracing::error!("Failed to notify dispatch engine: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    
    Ok(Json(PlanResponse {
        plan_uuid,
        status: "generating".to_string(),
    }))
}

#[derive(Serialize)]
pub struct CandidateResponse {
    pub id: String,
    pub name: String,
    pub profile: serde_json::Value,
    pub status: String,
}

pub async fn list_candidates_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    
    let candidates = hire::list_pending_candidates(&state.db_pool).map_err(|e| {
        tracing::error!("Failed to list candidates: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    
    let result: Vec<CandidateResponse> = candidates.iter().map(|c| {
        let profile: serde_json::Value = serde_json::from_str(&c.profile).unwrap_or(serde_json::json!({}));
        CandidateResponse {
            id: c.candidate_uuid.clone(),
            name: c.name.clone(),
            profile,
            status: c.status.clone(),
        }
    }).collect();
    
    Ok(Json(serde_json::json!({"pending": result})))
}
```

- [ ] **Step 2: 在 `src/api/router.rs` 中添加新路由**

找到 `/api/hiring/pending` 路由所在行，将现有 `hire::list_handler` 替换为 `hire::list_candidates_handler`，并添加 plan 路由：

```rust
.route("/api/hiring/plan", axum::routing::post(hire::plan_handler))
.route("/api/hiring/pending", axum::routing::get(hire::list_candidates_handler))
```

保留 approve 和 reject 路由不变。

- [ ] **Step 3: 更新 `src/api/hire.rs` 的 imports**（添加缺失的导入）

```rust
use axum::http::HeaderMap;
use crate::db::tasks;
use crate::db::models::NewTask;
use crate::dispatch::engine::TaskEvent;
```

- [ ] **Step 4: Commit**

```bash
git add src/api/hire.rs src/api/router.rs
git commit -m "feat: add hire plan API endpoints"
```

### Task 4.3: 更新前端 Hiring 页面适配新 API

**Files:**
- Modify: `web-ui/src/pages/Hiring.tsx`
- Modify: `web-ui/src/api/hiring.ts`

- [ ] **Step 1: 修改 `web-ui/src/api/hiring.ts`，新增 `createPlan()`**

```typescript
export interface HirePlanRequest {
  position: string
  skills?: string
  responsibilities?: string
  traits?: string
  count?: number
}

export interface HirePlanResponse {
  plan_uuid: string
  status: string
}

export const hiringApi = {
  listPending: () => api.get<{ pending: PendingHire[] }>("/hiring/pending"),
  approve: (hireId: string, profile?: Record<string, unknown>) =>
    api.post<{ status: string; hire_id: string }>(`/hiring/${hireId}/approve`, profile ?? {}),
  reject: (hireId: string) =>
    api.post<{ status: string; hire_id: string }>(`/hiring/${hireId}/reject`, {}),
  createPlan: (data: HirePlanRequest) =>
    api.post<HirePlanResponse>("/hiring/plan", data),
}
```

- [ ] **Step 2: 修改 `Hiring.tsx` 中的 `submitPlan` 函数**

```typescript
async function submitPlan() {
  if (!position.trim()) return
  setSubmitting(true)
  try {
    await hiringApi.createPlan({
      position: position.trim(),
      skills,
      responsibilities,
      traits,
      count,
    })
    toast.success("Hiring plan submitted to Leader")
    setPosition(""); setSkills(""); setResponsibilities(""); setTraits("")
  } catch {
    toast.error("Failed to submit plan")
  } finally {
    setSubmitting(false)
  }
}
```

- [ ] **Step 3: 适配候选人数据结构**（确保 `PendingHire` 接口匹配后端返回）

`PendingHire` 接口已匹配 `CandidateResponse`：
```typescript
export interface PendingHire {
  id: string  // candidate_uuid
  name: string
  profile: {
    role: string
    objective: string
    traits: string[]
    background: string
    rules: string[]
  }
  status: string
}
```
无需修改接口定义，但需确认 approve/reject 使用 candidate_uuid 正确。

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/api/hiring.ts web-ui/src/pages/Hiring.tsx
git commit -m "feat: update Hire page to use new AI plan API"
```

---

## 自检清单

- [ ] Phase 1: Provider Test指向具体实现的正确端点
- [ ] Phase 1: `make_provider_by_name()`被 `test_provider()` 调用
- [ ] Phase 2: `providersApi` import 正确
- [ ] Phase 2: `hasConfiguredProvider` 检查逻辑正确
- [ ] Phase 2: `useMemo` import 已添加（用于 failedMessages）
- [ ] Phase 3: usage 字段名同时兼容 `prompt_tokens` 和 `input_tokens`
- [ ] Phase 3: COCOCAT_WORKSPACE 路径覆盖正确
- [ ] Phase 4: `hire::plan_handler` 中 `NewTask` 和 `tasks` 导入正确
- [ ] Phase 4: 迁移 SQL 正确创建两个新表
- [ ] Phase 4: 候选人 `profile` 存储为 JSON 字符串，前端解析一致
