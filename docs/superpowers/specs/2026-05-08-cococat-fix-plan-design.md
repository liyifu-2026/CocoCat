# CocoCat 核心问题修复设计

## 概述

本文档针对 CocoCat 系统中 4 个核心问题进行修复设计：Hire 页面不可用、Usage 页面无数据、LLM Provider 配置系统问题、Chat 页面缺少错误提示。

## Phase 1: LLM Provider 系统修复

### 问题分析

1. **Test 功能 bug**: `web/routes/providers.py:104` 中 `test_provider()` 调用 `make_provider(f"{name}/test")`，导致 `find_by_model("deepseek/test")` 尝试匹配模型名而非 provider name。当 API key 仅存在于 `config/auth.json` 而未设置对应 env var时，spec 会被跳过。
2. **`.env` 依赖混淆**: 启动需要的 `.env` 变量实际是 `JWT_SECRET`/`API_KEY`（用于认证），而非 LLM API key。用户误以为需要在 `.env` 中设置 LLM API key。

### 改动清单

| 文件 | 改动 |
|------|------|
| `py-agent/providers/factory.py` | `make_provider()` 增加对 `auth.json` 的检查，不只看 env var |
| `web/routes/providers.py` | `test_provider()` 改为 `make_provider(name)` 而非 `make_provider(f"{name}/test")` |
| `py-agent/providers/factory.py` | 新增 `make_provider_by_name(name)` 通过 provider name 直接构造，不经过 model 匹配 |
| 文档 | 澄清 `.env` 必需项仅为认证相关，LLM API key 完全通过 UI 配置 |

### 数据流

```
Frontend Test按钮 → POST /api/providers/{name}/test
  → Python FastAPI test_provider()
  → make_provider_by_name(name)
  → get_api_key(name): auth.json → env var → OPENAI_API_KEY
  → GET {api_base}/v1/models (实际测试连接)
  → 返回 {status: "ok", models: [...]}
```

## Phase 2: Chat 页面分层错误提示

### 问题分析

`Chat.tsx` 中 `sendMessage()` 的 catch 块仅恢复 UI 状态（`setLocalStreaming(false)` + 回退消息列表），没有给用户任何可见的错误提示。后端的 `task_failed` WebSocket 事件也没有在 UI 上展示。

### 改动清单

| 文件 | 改动 |
|------|------|
| `web-ui/src/pages/Chat.tsx` | `sendMessage()` catch 块增加 toast 错误提示 |
| `web-ui/src/pages/Chat.tsx` | 监听 `streamState` 中的 failed 事件，在消息列表中插入系统错误消息 |
| `web-ui/src/pages/Chat.tsx` | 输入区域增加 provider 配置状态检查，未配置时显示黄色提示条并禁用发送按钮 |

### 分层提示逻辑

```
第一层: 输入框上方
  ┌──────────────────────────────────────────────┐
  │ ⚠️ API Key 未配置，请前往 设置 页面配置后再试  │
  │ [发送按钮已禁用]                               │
  └──────────────────────────────────────────────┘

第二层: 发送失败后（catch 块）
  → toast.error("发送失败: 请检查 API Key 配置")
  → 消息列表中显示红色系统错误气泡

第三层: WebSocket task_failed 事件
  → 自动监听 streamState
  → 在对话中插入:
    ┌──────────────────────────────────────────┐
    │ ❌ Agent 回复失败: <具体错误信息>          │
    └──────────────────────────────────────────┘
```

## Phase 3: Usage 页面数据修复

### 问题分析

**核心 bug**: `agent_loop.py:370-371` 从 LLM API 响应中读取 `input_tokens` 和 `output_tokens`，但 OpenAI 兼容 API 返回的字段名为 `prompt_tokens` 和 `completion_tokens`。

```python
# agent_loop.py:370-371 (现有代码 - 错误的字段名)
total_usage["input"] += u.get("input_tokens", 0) or 0    # 永远返回 0
total_usage["output"] += u.get("output_tokens", 0) or 0   # 永远返回 0

# agent_loop.py:464 (因此永远不会进入)
if total_usage.get("input", 0) or total_usage.get("output", 0):
    _log_usage(...)  # 从不执行
```

**路径一致性确认**:
- Python agent 写入: `/home/leaif/CocoCat/agents/_usage.jsonl` ✓
- Rust API 读取: `env!("CARGO_MANIFEST_DIR")/agents/_usage.jsonl` ✓
- Python FastAPI 读取: `BASE_DIR/agents/_usage.jsonl` ✓
- 三个路径解析结果一致，不存在路径问题

### 改动清单

| 文件 | 改动 |
|------|------|
| `py-agent/agent_loop.py:370-371` | 将 `u.get("input_tokens", 0)` 改为 `u.get("prompt_tokens", 0)` |
| `py-agent/agent_loop.py:370-371` | 将 `u.get("output_tokens", 0)` 改为 `u.get("completion_tokens", 0)` |
| `web-ui/src/pages/TokenUsage.tsx` | 空状态增加引导提示，指向 Chat 页面 |
| `src/db/usage.rs` | 增加 `COCOCAT_WORKSPACE` env var 支持覆盖路径 |

### 修复后数据流

```
Agent 调用 LLM
  → API 返回 {usage: {prompt_tokens: 100, completion_tokens: 50}}
  → agent_loop 读取 prompt_tokens/completion_tokens
  → total_usage = {input: 100, output: 50}
  → _log_usage() 写入 agents/_usage.jsonl
  → Frontend GET /api/usage?limit=100
  → 读取文件并返回 [{agent_id, input_tokens, output_tokens, ...}]
  → TokenUsage.tsx 显示具体数值
```

## Phase 4: Hire 页面 AI 招聘流程

### 问题分析

现有 Hire 系统有两层矛盾：
1. 前端 UI 设计为"AI 招聘流程"（提交需求 → AI 生成候选人 → 审批）
2. 后端 Rust API 仅支持直接 "hire request"（指定 agent_id/name 雇佣已知 agent）
3. 前端 `submitPlan()` 调用 `POST /api/hiring/plan` 但后端只有 `POST /api/hiring/request`
4. 前后端数据模型完全不匹配（前端期待 `profile:{role, objective, traits, background}`，后端返回 `request_uuid, requester_agent, ...`）

### 架构设计

采用 **Rust Dispatch** 方案，复用现有任务调度系统：

```
POST /api/hiring/plan
{
  position: "Customer Support Specialist",
  skills: "patience, communication",
  responsibilities: "...",
  traits: "detail-oriented",
  count: 5
}
  → Rust plan_handler
  → 创建 task 给 "leader" agent, method: "hire_plan"
  → 写入 hire_plans 表, status: "generating"
  → 返回 {plan_id}

Leader Agent 处理:
  → 读取 task params {position, skills, ...}
  → 调用 LLM 生成候选人档案列表
  → 写入 hire_candidates 表, 每个 candidate status: "pending"
  → 更新 plan status: "completed"
  → 广播 WebSocket 通知

前端轮询 GET /api/hiring/pending:
  → 返回 [{id, name, profile:{role, objective, traits, background, rules}, status}]

前端审批 POST /api/hiring/:candidate_id/approve:
  → 创建 agent 目录 + config.toml 条目
  → 写入 profile.json

前端拒绝 POST /api/hiring/:candidate_id/reject:
  → 更新 status 为 rejected
```

### 改动清单

| 文件 | 改动 |
|------|------|
| `src/api/router.rs` | 新增 `POST /api/hiring/plan` 路由 |
| `src/api/hire.rs` | 新增 `plan_handler` 处理招聘计划提交 |
| `src/db/hire.rs` | 新增 `hire_plans` 和 `hire_candidates` 表及 CRUD |
| `src/dispatch/engine.rs` | 支持 `method: "hire_plan"` 的任务分发（如需要） |
| `py-agent/agent_runtime.py` | 支持 `hire_plan` method，Leader agent 生成候选人 |
| `web-ui/src/api/hiring.ts` | 新增 `createPlan()` API |
| `web-ui/src/pages/Hiring.tsx` | 适配新的候选人数据结构，增加轮询逻辑 |

### 数据库 schema

```sql
CREATE TABLE hire_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_uuid TEXT NOT NULL UNIQUE,
    position TEXT NOT NULL,
    skills TEXT,
    responsibilities TEXT,
    traits TEXT,
    requested_count INTEGER DEFAULT 5,
    status TEXT DEFAULT 'generating',  -- generating, completed, failed
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE hire_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_uuid TEXT NOT NULL UNIQUE,
    plan_uuid TEXT NOT NULL REFERENCES hire_plans(plan_uuid),
    name TEXT NOT NULL,
    profile TEXT NOT NULL,  -- JSON: {role, objective, traits, background, rules}
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    created_at TEXT DEFAULT (datetime('now')),
    decided_at TEXT,
    reviewer TEXT
);
```

## 依赖关系

```
Phase 1 Provider修复 ──────────────────────────┐
       │                                        │
       ▼                                        ▼
Phase 2 Chat错误提示 ──── 依赖 Provider 可用 ──▶ 确保系统能运行
       │
       ▼
Phase 3 Usage数据修复 ──── 依赖系统实际运行产生数据
       │
       ▼
Phase 4 Hire招聘流程 ──── 依赖 Dispatch 系统正常工作
```

## 验证方式

1. Phase 1: 在 UI 中配置 API key → Test 按钮返回 `Connected` → 重启后配置仍在
2. Phase 2: 在 Chat 页面尝试发送消息，当无 API key 时看到分层提示；配置 key 后成功发送
3. Phase 3: Chat 成功后，Usage 页面显示 token 用量数据
4. Phase 4: 提交招聘计划 → Leader 生成候选人 → 审批通过后 agent 出现在列表中
