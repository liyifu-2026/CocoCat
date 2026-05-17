---
title: API 端点
sidebar_position: 6
---

# API 端点

FastAPI 路由表。所有端点(除 `/api/auth/login`、`/api/auth/verify`)需要 `Authorization: Bearer <JWT>` 头。

## 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录,返回 JWT token |
| GET | `/api/auth/verify` | 验证 token 有效性 |

## Agent 管理 (`cococat/routes/agents.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents` | 列出所有 agent 及状态 |
| GET | `/api/agents/{id}` | 获取单个 agent 详情 |
| POST | `/api/agents` | 创建新 agent |
| PUT | `/api/agents/{id}` | 更新 agent |
| DELETE | `/api/agents/{id}` | 删除 agent |
| GET | `/api/agents/{id}/profile` | 获取 agent 个性配置 |
| PUT | `/api/agents/{id}/profile` | 更新 agent 个性 |
| GET | `/api/agents/{id}/skills` | 列出 agent 技能 |
| GET | `/api/agents/{id}/memory` | 读取 agent 记忆(MEMORY.md) |
| GET | `/api/agents/{id}/history` | 读取 agent 历史(history.jsonl) |
| GET | `/api/agents/{id}/display` | 获取显示配置 |
| PUT | `/api/agents/{id}/display` | 更新显示配置 |

## 场景管理 (`cococat/routes/scenes.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scenes` | 列出所有场景 |
| POST | `/api/scenes` | 创建场景 |
| DELETE | `/api/scenes/{id}` | 删除场景 |
| GET | `/api/scenes/{id}/context` | 获取场景 CONTEXT.md |
| PUT | `/api/scenes/{id}/context` | 更新场景 CONTEXT.md |
| GET | `/api/scenes/{id}/kbs` | 获取挂载的知识库 |
| POST | `/api/scenes/{id}/kbs` | 挂载知识库 |
| DELETE | `/api/scenes/{id}/kbs/{kb_id}` | 卸载知识库 |
| GET | `/api/scenes/{id}/roster` | 获取场景成员列表 |
| POST | `/api/scenes/{id}/roster` | 添加成员 |
| DELETE | `/api/scenes/{id}/roster/{agent_id}` | 移除成员 |
| GET | `/api/scenes/{id}/skills` | 获取场景技能 |
| PUT | `/api/scenes/{id}/skills` | 更新场景技能 |
| POST | `/api/scenes/{id}/chat` | 场景对话(外部入口) |
| GET | `/api/scenes/{id}/users/{uid}/history` | 获取用户对话历史 |

## 知识库 (`cococat/routes/knowledge.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge` | 列出所有知识库 |
| POST | `/api/knowledge` | 创建知识库 |
| DELETE | `/api/knowledge/{id}` | 删除知识库 |
| GET | `/api/knowledge/{id}/wiki` | 列出 Wiki 页面 |
| GET | `/api/knowledge/{id}/wiki/{slug}` | 获取 Wiki 页面内容 |
| POST | `/api/knowledge/{id}/wiki` | 创建 Wiki 页面 |
| PUT | `/api/knowledge/{id}/wiki/{slug}` | 更新 Wiki 页面 |
| DELETE | `/api/knowledge/{id}/wiki/{slug}` | 删除 Wiki 页面 |
| GET | `/api/knowledge/{id}/search` | 搜索知识库 |

## 聊天群组 (`cococat/routes/chat_groups.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/chat` | 读取聊天记录 |
| GET | `/api/chat/groups` | 列出群组 |
| POST | `/api/chat/groups` | 创建群组 |
| DELETE | `/api/chat/groups/{id}` | 删除群组 |
| GET | `/api/chat/groups/{id}/messages` | 获取群消息 |
| POST | `/api/chat/groups/{id}/messages` | 发送群消息 |

## 邮箱 (`cococat/routes/mailbox.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/mailbox/{agent_id}` | 查看邮箱(收件箱) |
| POST | `/api/mailbox/send` | 发送消息 |
| PUT | `/api/mailbox/{agent_id}/read/{idx}` | 标记已读 |

## Hiring (`cococat/app.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/hiring/pending` | 列出待审批的 hire 请求 |
| POST | `/api/hiring/pending/{id}/approve` | 批准 hire |
| POST | `/api/hiring/pending/{id}/reject` | 拒绝 hire |

## 定时任务 (`cococat/routes/schedule.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/schedule` | 列出定时任务 |
| POST | `/api/schedule` | 创建定时任务 |
| PUT | `/api/schedule/{id}` | 更新定时任务 |
| DELETE | `/api/schedule/{id}` | 删除定时任务 |

## 状态 (`cococat/routes/status.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents/status` | 所有 agent 运行状态 |
| GET | `/api/status` | 系统总体状态 |
| GET | `/api/usage` | Token 用量统计 |

## 协作 (`cococat/routes/collaboration.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/collaboration/graph` | 获取 agent 协作关系图 |

## 入口 (`cococat/routes/entries.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/entries` | 列出所有频道入口配置 |
| POST | `/api/entries` | 创建频道入口 |
| DELETE | `/api/entries/{id}` | 删除频道入口 |

## 外部通道

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/channels/wechat/{scene_id}` | 微信公众号 webhook |
| POST | `/api/channels/webhook/{type}/{id}` | 通用 webhook 入口 |

## WebSocket

| 路径 | 参数 | 说明 |
|------|------|------|
| `/ws` | `?token=` | 实时推送(心跳、事件) |
