# Agents Settings 重设计

## 决策

| # | 问题 | 决策 |
|---|------|------|
| 1 | 页面范围 | Coco 主代理 + 子代理默认配置（两个角色，左右切换） |
| 2 | 交互模式 | 角色卡 + ◀▶ 切换，一次只看一个角色 |
| 3 | Coco 配置项 | 模型选择 + 自定义 System Prompt（可恢复默认） |
| 4 | 子代理配置项 | 默认模型选择（所有临时 sub-agent 共用） + 说明文字 |
| 5 | 子代理实例 | 不展示具体 worker 实例列表（用完即销毁，无持久状态） |
| 6 | 子代理 prompt | 不可自定义，使用默认系统 prompt |

## UI 布局

```
┌─────────────────────────────────────────────┐
│                                              │
│      ◀    ┌──────────────────┐    ▶         │
│           │       🧠          │              │
│           │      主代理        │              │
│           │    协调者          │              │
│           └──────────────────┘              │
│                                              │
│ ┌─ 核心引擎 ───────────────────────────────┐ │
│ │  LLM 模型    [ 🔮 deepseek-chat  ▼ ]    │ │
│ └───────────────────────────────────────────┘ │
│                                              │
│ ┌─ 思维中枢 ───────────────────────────────┐ │
│ │  System Prompt                            │ │
│ │  ┌──────────────────────────────────────┐ │ │
│ │  │ You are Coco — a task orchestrator   │ │ │
│ │  │ ...                                  │ │ │
│ │  └──────────────────────────────────────┘ │ │
│ │  [恢复默认]  [保存]                        │ │
│ └───────────────────────────────────────────┘ │
│                                              │
└─────────────────────────────────────────────┘
```

Worker 视图：角色卡不同，去掉思维中枢，只留默认模型 + 说明。

## 功能

### Coco（主代理）

- **模型选择**：下拉列表，来自已配置供应商的启用模型（和 Chat 页模型选择同数据源）
- **System Prompt**：可编辑 textarea，默认值为 `prompt.py` 的 `STATIC_PREFIX`
- **保存**：保存到后端（存文件或 DB），重启后生效
- **恢复默认**：一键重置为 `STATIC_PREFIX`

### Worker（子代理模板）

- **默认模型**：下拉选择，所有 `LocalExecutor` 创建的 sub-agent 用此模型
- **说明文字**：静态提示"子代理按需创建，任务完成后自动销毁"
- **无 prompt 配置**

## 后端改动

### 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/agents/main/prompt` | 获取 Coco 当前 system prompt（自定义或默认） |
| `PUT` | `/api/agents/main/prompt` | 保存 Coco 自定义 system prompt |
| `DELETE` | `/api/agents/main/prompt` | 恢复默认 system prompt |
| `GET` | `/api/agents/config` | 获取子代理默认模型 |
| `PUT` | `/api/agents/config` | 保存子代理默认模型 |

### 数据存储

- Coco system prompt：`config/prompts/coco.md`（或 agents/main/prompt.md）
- 子代理默认模型：`config/defaults.json` → `{"worker_model": "deepseek-chat"}`

### `get_llm` 改动

`__main__.py` 的 `get_llm(agent_id)` 函数需要用子代理默认模型作为 fallback，替代当前硬编码的 `deepseek-chat`。

## 实现步骤

1. 后端：新增 prompt 读写 API + worker 默认模型 API
2. 后端：`get_llm` 改从配置读默认模型
3. 前端：重写 `AgentsTab` → 角色切换 + Coco 配置 + Worker 配置
4. 测试
