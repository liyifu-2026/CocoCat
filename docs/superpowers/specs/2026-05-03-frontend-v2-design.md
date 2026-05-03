# CocoCat Frontend v2: Agent Detail + Knowledge Base

## Overview

完善前端 v1 的 Agent 详情页 Tab，新增知识库浏览页面。后端新增对应 REST API，前端借鉴 llm-wiki 的 WikiReader 和 KnowledgeTree 模式。

## Scope

1. **后端新增 API** — Agent 详情 4 个端点 + Knowledge 3 个端点
2. **前端 Agent 详情完善** — 4 个 Tab 从占位文本改为真实数据
3. **前端 Knowledge 页面** — 左侧知识树 + 右侧内容阅读器

## Backend API

### Agent Detail (新增到 `web/routes/agents.py`)

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/agents/{id}` | Agent detail |
| GET | `/api/agents/{id}/profile` | profile.json 内容 |
| GET | `/api/agents/{id}/skills` | skills/manifest.json 内容 |
| GET | `/api/agents/{id}/memory` | MEMORY.md 纯文本 |
| GET | `/api/agents/{id}/history` | history.jsonl 条目列表 |

### Knowledge (新增 `web/routes/knowledge.py`)

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/knowledge` | KB 列表（已有，增强返回 purpose/schema/index） |
| GET | `/api/knowledge/{kb}` | KB 详情（purpose、schema、index 等元数据） |
| GET | `/api/knowledge/{kb}/wiki` | wiki 页面列表（按 entity/concept/source 分组） |
| GET | `/api/knowledge/{kb}/wiki/{type}/{name}` | wiki 页面 markdown 内容 |

## Frontend Agent Detail

修改 `web-ui/src/pages/AgentDetail.tsx`，4 个 Tab 改为从 API 加载：

**Profile Tab**
- `useQuery` 调 `/api/agents/{id}/profile`
- 显示 role、objective、traits（Badge 组件）、rules（列表）、background

**Skills Tab**
- `useQuery` 调 `/api/agents/{id}/skills`
- 分 public / private 两组 Card 展示

**Memory Tab**
- `useQuery` 调 `/api/agents/{id}/memory`
- `<pre>` 渲染 markdown 内容

**History Tab**
- `useQuery` 调 `/api/agents/{id}/history`
- 表格展示 timestamp、prompt、response

## Frontend Knowledge Page

借鉴 llm-wiki 的 KnowledgeTree 和 WikiReader 组件。

### Pages 结构

```
/knowledge            → Knowledge 列表页（KB 卡片网格）
/knowledge/{kb}       → Knowledge 详情页（知识树 + wiki 阅读器）
```

### Knowledge 详情页布局

```
┌─────────────────────────────────────────────┐
│ ┌──────────────┐  ┌────────────────────────┐ │
│ │ Knowledge    │  │  Wiki Reader           │ │
│ │ Tree         │  │                        │ │
│ │              │  │  ## Entity Title       │ │
│ │ ─ Entities   │  │  content...            │ │
│ │   ├ 实体A    │  │                        │ │
│ │   └ 实体B    │  │  | col1 | col2 |       │ │
│ │ ─ Concepts   │  │  |------|------|       │ │
│ │ ─ Sources    │  │                        │ │
│ │              │  │  [[wikilinks]]         │ │
│ └──────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### 左侧：KnowledgeTree（借鉴 llm-wiki）

- 按 entity / concept / source 分组
- 可折叠，显示各类型数量
- 点击加载 wiki 内容到右侧

### 右侧：WikiReader（从 llm-wiki 直接复制）

- react-markdown 渲染
- 支持表格、代码块、图片
- 简化版，去掉 Tauri 依赖

## Dependencies Added

```json
{
  "react-markdown": "^10.x",
  "remark-gfm": "^4.x",
  "remark-math": "^6.x",
  "rehype-katex": "^7.x",
  "katex": "^0.16.x"
}
```

## Implementation Order

1. 后端 Agent 详情 API
2. 后端 Knowledge API
3. 前端 AgentDetail Tab 完善
4. 前端 Knowledge 列表页
5. 前端 Knowledge 详情页（KnowledgeTree + WikiReader）
