# Agent & Scene Management UI

## Overview

为 Agent 和 Scene 增加编辑管理功能。当前是只读展示，改为可操作管理。

## Backend API

### Agent Management (新增到 `web/routes/agents.py`)

| Method | Path | Body | 说明 |
|--------|------|------|------|
| PATCH | `/api/agents/{id}` | `{name?, scene?, enabled?}` | 更新 agent 配置 |
| PATCH | `/api/agents/{id}/skills` | `{public?: [...], private?: [...]}` | 替换技能清单 |
| DELETE | `/api/agents/{id}` | - | 删除 agent（解雇） |

### Scene Management (新增 `web/routes/scenes.py`)

| Method | Path | Body | 说明 |
|--------|------|------|------|
| POST | `/api/scenes` | `{id, context?}` | 创建场景 |
| DELETE | `/api/scenes/{id}` | - | 删除场景 |
| PATCH | `/api/scenes/{id}/context` | `{context}` | 更新 CONTEXT.md |
| PATCH | `/api/scenes/{id}/kbs` | `{mounted: [...]}` | 挂载/卸载 KB |
| PATCH | `/api/scenes/{id}/roster` | `{agents: [...]}` | 分配/移除 agent |
| PATCH | `/api/scenes/{id}/skills` | `{env_skills: [...]}` | 管理 env skills |

## Frontend

### Agent Detail 增加编辑模式

- Profile tab → 只读（不可变）
- Skills tab → 改为可编辑：添加/删除 public/private 技能
- 页面顶部增加启用/禁用开关
- 底部增加"解雇"按钮（确认弹窗）

### Scenes 页面增加编辑

- 列表页增加"创建场景"按钮 + 对话框
- 详情页：
  - CONTEXT.md 可编辑
  - KB 挂载列表可添加/移除
  - Roster 可添加/移除 agent
  - Env skills 可添加/删除
  - 底部"删除场景"按钮（确认弹窗）

## Files Changed

| File | Change |
|------|--------|
| `web/routes/agents.py` | 3 个新端点 |
| `web/routes/scenes.py` | 新文件，6 个端点 |
| `web/main.py` | 注册 scene router |
| `web-ui/src/api/agents.ts` | 新增 update/delete 等方法 |
| `web-ui/src/api/scenes.ts` | 新增 create/update/delete 等方法 |
| `web-ui/src/pages/AgentDetail.tsx` | 增加编辑模式 |
| `web-ui/src/pages/Scenes.tsx` | 增加创建场景 |
| `web-ui/src/pages/SceneDetail.tsx` | 增加编辑功能 |
