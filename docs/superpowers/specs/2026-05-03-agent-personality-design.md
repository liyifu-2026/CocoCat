# Agent Personality System

## Overview

为 CocoCat 的智能员工增加不可变的个性化配置，采用"结构化模板 + 自由文本扩展"的 Hybrid 模式。个性在 hire 时由 Leader 填写，人工确认后写入，之后不可修改。

## Personality Schema

每个 agent 拥有一份 `profile.json`，存放于 `agents/{agent_id}/profile.json`：

```json
{
  "role": "资深工程师",
  "objective": "执行严格的代码审查，指出潜在漏洞并提供重构建议",
  "traits": ["细心", "严谨", "语气:专业", "篇幅:适中"],
  "background": "（可选自由文本）",
  "rules": ["代码必须经过review才能合并", "优先使用异步IO"]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `role` | string | 一句话角色定位，自由文本 |
| `objective` | string | 核心目标/使命 |
| `traits` | string[] | 特质标签，支持 `key:value` 格式（如 `语气:专业`） |
| `background` | string | 可选背景故事，自由文本 |
| `rules` | string[] | 行为准则列表 |

## Hire Flow (Two-Phase)

### Phase 1: 创建待确认需求

Leader 通过 `HireAgentTool`（扩展参数增加 profile 字段）创建 hire request：

```
agents/hire_requests/pending/{id}.json
```

```json
{
  "id": "new_employee",
  "name": "新员工",
  "scene": "development",
  "profile": {
    "role": "...",
    "objective": "...",
    "traits": ["..."],
    "background": "",
    "rules": ["..."]
  },
  "status": "pending"
}
```

### Phase 2: 人工确认

支持两个确认入口，互斥处理：

**终端确认**：Rust `process_hire_requests()` 扫描 `pending/` 目录，通过 `_ask_user.json` 呈现给操作员。操作员可修改或直接确认。确认后文件移入 `agents/hire_requests/approved/`。

**Web 面板确认**：FastAPI 新增端点：
- `GET /api/hiring/pending` — 列出待确认需求
- `POST /api/hiring/pending/{id}/approve` — 确认（body 可选包含修改后的 profile）
- `POST /api/hiring/pending/{id}/reject` — 拒绝

冲突处理：已处理文件加 `.processed` 后缀锁，防止终端和 Web 重复操作。

### Phase 3: 执行 Hire

Rust `process_hire_requests()` 只扫描 `approved/` 目录，执行：

1. 写 `agents/{id}/profile.json`
2. 写 `agents/{id}/memory/MEMORY.md`（已有）
3. 追加 `[[agents]]` 到 `config.toml`（已有）
4. spawn 新 agent（已有）
5. 从 `approved/` 移除文件

## Immutability Guarantee

两重防护确保 profile 不可变：

- **Rust 侧**：hire 时检查 `agents/{id}/profile.json`，已存在则跳过写入。不提供任何修改 profile 的 API 或工具。
- **Python 侧**：不提供任何写 profile.json 的工具。`context.py` 只读不写。

如需重新 hire，须手动删除整个 agent 目录后重新走 hire 流程。

## System Prompt Injection

`context.py` 的 `build_system_prompt()` 在 Identity 段后增加 Profile 段：

```
## Your Profile
角色: {role}
目标: {objective}
特质: {traits}
行为准则:
- {rule1}
- {rule2}

背景故事:
{background}
```

`agent_loop.py` 初始化时自动读取 `agents/{id}/profile.json` 传入 `build_system_prompt()`。

## Files Changed

| File | Change |
|------|--------|
| `py-agent/context.py` | `build_system_prompt()` 增加 profile 参数和模板段 |
| `py-agent/agent_loop.py` | 初始化时读取 profile.json |
| `py-agent/tools.py` | `HireAgentTool` 参数增加 profile 字段 |
| `src/main.rs` | `process_hire_requests()` 改为两阶段：扫描 pending → 确认 → 扫描 approved → 执行 |
| `web/main.py` | 新增 `/api/hiring/pending`、`/api/hiring/pending/{id}/approve`、`/api/hiring/pending/{id}/reject` 端点 |
| (new) `agents/{agent_id}/profile.json` | 新 hire 的 agent 自动生成 |
