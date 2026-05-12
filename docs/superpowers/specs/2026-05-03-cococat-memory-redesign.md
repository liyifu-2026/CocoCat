# CocoCat 记忆系统重构设计

日期: 2026-05-03
状态: 设计稿

## 背景

当前 CocoCat 的记忆机制存在多个问题：记忆内容混在一起（无分层）、无法回溯回滚、Dream 触发不合理、记忆增长不可控、测试覆盖不足、工具接口混乱。本设计参考 `references/nanobot` 的记忆模式，在现有架构基础上做「重构整合」。

## 1. 记忆分层（Memory Hierarchy）

### 现状

```
agents/{id}/memory/
├── MEMORY.md            # 一切混合：身份 + 知识 + 用户信息
├── history.jsonl        # 所有用户的任务混在一起
└── .dream_cursor
```

### 新设计：三层记忆模型

```
agents/{agent_id}/memory/
├── MEMORY.md              # Agent 亲身经验：模式、决策、操作习惯
│                          #   Dream 写入 | 始终注入 prompt
│                          #   不做外部知识（走 wiki）
│                          #   不做用户画像（走 user PROFILE）
│
├── history.jsonl          # Agent 内部任务记录（工具调用、自省）
│
├── users/                 # 【新增】按用户隔离
│   ├── {user_hash}/
│   │   ├── PROFILE.md     #   该用户偏好、习惯、重要事实
│   │   ├── history.jsonl  #   对话历史（同步自 scenes/{scene}/{user}/）
│   │   └── .dream_cursor  #   每个用户的 Dream 进度
│   └── ...
│
└── .dream_cursor          # 全局 Dream 进度
```

### 设计决策

- `users/` 用 user_hash 而非原始 user_id，避免特殊字符问题
- PROFILE.md 由 Dream 自动维护，Agent 不应直接写入
- history.jsonl 分两级：Agent 级存工具调用，User 级存对话历史

### 注入方式

系统提示注入从单一的 `{agent_memory}` 扩展为：

```
## 我的经验
{agent_memory}

## 当前用户
{user_profile}

## 对话历史
{user_conversation_history}
```

## 2. Dream 触发优化

### 现状

`len(unprocessed) >= 3` 固定阈值，无内容感知。

### 新触发逻辑

```
触发条件 = (A OR B) AND C

A. 数量触发：未处理条目 ≥ N 条
   N = max(3, min(10, 未处理总token / 2000))

B. 时间触发：距离上次 Dream ≥ 30 分钟且有未处理条目

C. 抑制条件：当前正在执行任务
   ── 标记 pending，不打断主流程
```

### Per-user Dream 流程

```
用户对话 → scenes/{scene}/{user}/history.jsonl
  │
  └─ (agent 处理该消息时同步)
       │
       ▼
agents/{agent}/memory/users/{user_hash}/history.jsonl
  │
  ├─▶ Dream (per-user)
  │     ├─ 分析该用户对话历史
  │     ├─ 提炼偏好、习惯、重要事实
  │     └─ 写入 users/{user_hash}/PROFILE.md
  │
  └─▶ 系统提示时注入 PROFILE.md
```

## 3. 用户感知注入

### 改动路径

**web API 路径** (`web/main.py` → `agent_runtime.py`):
- task 中增加 `user_id` 字段
- AgentLoop 接收 `user_id` 参数

**邮箱路径** (`entry_manager.py` → heartbeat → AgentLoop):
- AgentLoop.run() 增加 `user_id` 参数

**系统提示构造** (`context.py`):
- `build_system_prompt()` 增加 `user_id` 参数
- 新增 `load_user_profile(agent_id, user_id)` → 加载 PROFILE.md

## 4. GitStore 版本控制

为 MEMORY.md 和 PROFILE.md 引入轻量 Git 支持。

- 每个 agent 的 `memory/` 目录独立 `git init`
- 每次 Dream 写入后自动 `git add + git commit`
- 新增 `RevertMemoryTool` 用于回滚
- Web API 增加 `GET /api/agents/{id}/memory/history` 返回 git log
- 不引入复杂封装层，直接调用 git 命令

## 5. 工具接口简化

| 工具 | 新行为 |
|------|--------|
| `RememberTool` | 增加 `user_id` 参数：有 → 写入 PROFILE.md；无 → 写入 MEMORY.md |
| `RecallTool` | 增加 `user_id` 参数：有 → PROFILE.md + MEMORY.md；无 → 仅 MEMORY.md |
| `DreamTool` | 保持不变，内部支持 per-user Dream |
| `RevertMemoryTool` | 【新增】回滚最近一次 Dream commit |

## 6. 离线压缩（AutoCompact）

复用心跳线程（每300秒），Agent 空闲时：
- 检查每个 user 的 history.jsonl 是否超过 token 预算
- 超出 → 将旧条目压缩为摘要
- 压缩后更新 dream_cursor

与现有 `consolidate()`（会话内实时压缩）互补。

## 7. 时间标注

不引入 nanobot 的逐行 line-age 标注。改为：
- history.jsonl 保持已有 timestamp 字段
- Dream 写入时注明处理时间范围
- PROFILE.md 中按时间分组，便于淘汰过期信息

## 8. 测试覆盖

| 测试模块 | 覆盖内容 |
|---------|---------|
| `test_memory_hierarchy.py` | MEMORY.md / PROFILE.md 分层读写正确 |
| `test_dream_trigger.py` | 数量触发 / 时间触发 / 抑制条件 |
| `test_user_identity.py` | user_id 传入后正确注入系统提示 |
| `test_per_user_dream.py` | 每个用户独立 Dream、cursor、PROFILE.md |
| `test_git_store.py` | Dream 后自动 commit、revert 回滚 |
| `test_auto_compact.py` | 空闲压缩、压缩摘要格式 |

## 不在此次范围的内容

- 不会引入 nanobot 的 `SOUL.md` / `USER.md` 概念
- 不会引入 line-ages 逐行年龄标注
- 不会修改 `knowledge/team-wiki/` 知识库体系
- 不会修改 agent `profile.json` 的创建/使用方式
