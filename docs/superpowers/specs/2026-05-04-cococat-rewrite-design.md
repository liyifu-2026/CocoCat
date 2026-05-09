# CocoCat 重写设计文档

## 背景

CocoCat 是一个多 AI 智能体协作平台。当前版本存在三类致命问题：

- **架构：** 三个独立运行时（Rust 守护进程、Python Agent 子进程、FastAPI Web 后端）通过共享文件系统通信，无任何跨进程锁，并发必现数据损坏
- **安全：** 硬编码密钥已泄露；`shell=True` 命令执行+可绕过的正则沙箱构成 RCE 风险；插件系统可加载任意代码
- **性能：** 聊天日志使用读-改-写模式，每次写入 O(n)，持续运行必崩溃

根本原因：**系统以 JSON 文件形式存储所有持久化状态，用手写 JSON 文件模拟数据库，但缺少数据库的事务、并发控制和索引能力。**

## 核心原则

1. **单一权威（Single Source of Truth）：** SQLite 是唯一持久状态存储。废弃所有 JSON/TOML 文件。
2. **唯一写入者（Single Writer）：** 只有 Rust 核心读写 SQLite。Web 后端和 Python Agent 通过 Rust 的 HTTP API / stdio 通信，从不直接碰存储。
3. **无状态工人（Stateless Workers）：** Python Agent 子进程通过 stdin/stdout 的 JSON-RPC 接收和返回结果，不访问文件系统。任何 Agent 可随时被杀死和重启——无数据损失。
4. **事件驱动，非轮询：** 用 tokio async channels 和 `select!` 替代 `sleep(5)` 循环。

## 架构

```
┌──────────────┐     HTTP/WS      ┌───────────────────────────────────┐
│  React Front  │◄──────────────►│        Rust Core (tokio async)      │
│  (web-ui/)    │                │                                     │
├──────────────┤                │  ┌────────────┐  ┌──────────────┐  │
│  Channels     │◄─── HTTP ────►│  │ HTTP Server │  │ Agent Manager │  │
│  (WeChat, TG) │               │  │ (axum)      │  │ (process mgmt)│  │
└──────────────┘               │  ├────────────┤  ├──────────────┤  │
                                │  │ Dispatch    │  │ Event Bus    │  │
                                │  │ Engine      │  │ (tokio mpsc) │  │
                                │  ├────────────┤  ├──────────────┤  │
                                │  │ SQLite Layer│  │ Config/Hire  │  │
                                │  │ (rusqlite   │  │              │  │
                                │  │  + r2d2)    │  │              │  │
                                │  └──────┬─────┘  └──────────────┘  │
                                └─────────┼──────────────────────────┘
                                          │ JSON-RPC over stdio
                                 ┌────────▼──────────────────────────┐
                                 │     Python Agent Workers           │
                                 │  (stateless, no filesystem access)  │
                                 │  agent_loop.py + tools + llm.py   │
                                 └───────────────────────────────────┘
```

### 组件职责

- **Rust Core (tokio async):**
  - HTTP Server (axum)：处理前端和外部通道的 API 请求
  - Agent Manager：管理 Python 子进程生命周期（spawn、health check、restart、kill）
  - Dispatch Engine：从 SQLite 读取待处理任务，通过 JSON-RPC 发送给目标 Agent，处理结果写回
  - Event Bus (tokio mpsc)：内部事件通知（新任务、Agent 状态变更、超时）
  - SQLite Layer (rusqlite + r2d2)：所有持久化操作，WAL 模式，连接池

- **Python Agent Workers (stateless):**
  - 通过 stdin/stdout JSON-RPC 接收 task、task_stream、ping 请求
  - agent_loop.py：ReAct 循环（LLM 调用 + Tool 执行）
  - **不直接访问任何文件或 SQLite**
  - 默认模式下，agents 目录不可写

- **Web 后端：**
  - 不再直接读/写文件系统
  - 所有操作通过 Rust 的 HTTP API 间接完成
  - 可作为独立进程部署，也可作为 Rust 的插件

## SQLite Schema

```sql
-- 用户
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 取代 agents/config.toml
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    model TEXT NOT NULL,
    scene_id TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'stopped'
        CHECK (status IN ('stopped','running','error')),
    system_prompt TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',  -- JSON for extensions
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_heartbeat_at TEXT
);

-- 取代 chat/group.jsonl
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_uuid TEXT UNIQUE NOT NULL,
    agent_id TEXT REFERENCES agents(id),       -- NULL for user messages
    user_id TEXT REFERENCES users(id),         -- NULL for agent/system messages
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content TEXT NOT NULL,
    scene_id TEXT NOT NULL DEFAULT 'default',
    chat_group TEXT NOT NULL DEFAULT 'general',
    metadata TEXT NOT NULL DEFAULT '{}',       -- JSON: tool_calls, tool_call_id, etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_messages_scene_group
    ON messages(scene_id, chat_group, created_at);

-- 取代 agents/dispatch_queue/
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_uuid TEXT UNIQUE NOT NULL,
    target_agent TEXT NOT NULL REFERENCES agents(id),
    source TEXT NOT NULL,  -- 'user', 'system', 'web', 'channel', 'schedule'
    method TEXT NOT NULL,  -- 'chat', 'task', 'task_stream'
    params TEXT NOT NULL DEFAULT '{}',       -- JSON
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed','cancelled')),
    result TEXT,                             -- JSON, NULL until completed
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX idx_tasks_status_target
    ON tasks(status, target_agent)
    WHERE status IN ('pending','running');

-- 取代 agents/mailbox/
CREATE TABLE mailbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_uuid TEXT UNIQUE NOT NULL,
    from_agent TEXT NOT NULL REFERENCES agents(id),
    to_agent TEXT NOT NULL REFERENCES agents(id),
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 取代 agents/hire_requests/
CREATE TABLE hire_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_uuid TEXT UNIQUE NOT NULL,
    requester_agent TEXT NOT NULL REFERENCES agents(id),
    new_agent_id TEXT NOT NULL,
    new_agent_name TEXT NOT NULL,
    new_agent_role TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','rejected')),
    reviewer TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at TEXT
);

-- 取代 scenes/ 目录
CREATE TABLE scenes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    roster TEXT NOT NULL DEFAULT '[]',  -- JSON array of agent IDs
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 取代 skills/ 目录
CREATE TABLE skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('public','private','scene')),
    content TEXT NOT NULL,
    scene_id TEXT REFERENCES scenes(id),
    agent_id TEXT REFERENCES agents(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

## 数据流

### 用户发消息

```
POST /api/chat  →  axum handler
  1. 验证 JWT
  2. WAL 事务开始
  3. INSERT INTO messages (role='user', user_id=?, ...)
  4. INSERT INTO tasks (target_agent='leader', method='chat', status='pending')
  5. 事务提交
  6. tx.send(TaskEvent { task_id })  →  Dispatch Engine 收到通知
  7. UPDATE tasks SET status='running', started_at=now()
  8. 向对应 Agent 的 stdin 写 JSON-RPC request
  9. Agent 逐行返回 JSON-RPC response
  10. 每行 → INSERT INTO messages (role='assistant|tool', parent_msg_id=...)
  11. 最终响应 → UPDATE tasks SET status='completed', result=...
  12. 可选：WebSocket 推送到前端
```

### Agent 崩溃自动恢复

```
AgentManager 检测子进程退出
  1. UPDATE agents SET status='error', last_heartbeat_at=now()
  2. SELECT * FROM tasks WHERE status='running' AND target_agent=?
  3. 对每个运行中的任务：
     若 retry_count < max_retries：
       → UPDATE tasks SET status='pending', retry_count=retry_count+1
     否则：
       → UPDATE tasks SET status='failed', error='agent crashed'
  4. AgentManager 自动重启子进程
     → UPDATE agents SET status='running'
     → Dispatch Engine 重新调度 pending 任务（通过 tokio channel 通知）
```

### 任务不丢失保证

- 任务 INSERT 和消息 INSERT 在同一 SQLite 事务中
- Agent 的每行 stdout 响应由 Rust 读取并持久化后才处理下一条
- 如果 Rust 崩溃：重启后扫描 `status='running'` 的任务，按规则重新调度
- SQLite WAL 模式：崩溃最多丢失最后几条未提交数据，不影响已提交数据

## 安全性

| 问题 | 方案 |
|------|------|
| `shell=True` 命令注入 | 工具接收结构化参数 `[program, arg1, ...]`，禁止 shell |
| 正则沙箱可绕过 | 废弃正则沙箱，默认启用 Linux namespace 隔离（`unshare --net --pid --mount`） |
| 插件系统 RCE | 插件在独立受限子进程中运行 |
| JWT 空密钥 | 启动时校验 `JWT_SECRET`，空值或等于已知开发用值则拒绝启动 |
| CORS 通配符 + credentials | 显式配置 origins，启动时校验 |
| 密钥在 .env 中提交 | `.env` 移入 `.gitignore`；加载失败时打印清晰错误信息 |
| Agent 访问文件系统 | 默认禁止；需要时通过工具参数白名单控制 |

## 迁移策略

### Phase 1 — 最小可运行核心

目标：一个能启动、能接受消息、能调用 Agent 并返回结果的系统。

1. 新建 Rust 项目，依赖：tokio, axum, rusqlite (bundled), r2d2, serde, serde_json, tracing, tokio-util (for async pipes)
2. 实现 SQLite 初始化 + 连接池
3. 实现 `agents` 和 `messages` 表的读写
4. 实现 `agent_manager.rs`：spawn Python 子进程，stdin/stdout JSON-RPC，health check
5. 实现 `dispatch_engine.rs`：读取 tasks 表，通过 channel 通知，发送给 Agent
6. 实现 axum HTTP API：`POST /api/chat`（单条消息）
7. Python 端：`agent_loop.py` 保持基本不变，移除文件系统 I/O

### Phase 2 — 功能对等

1. 实现 `tasks` 表完整生命周期（retry、timeout、cancellation）
2. 实现 `mailbox` 表 + API
3. 实现 `hire_requests` 表 + API
4. 实现 `scenes` 表 + API
5. 实现 `skills` 表 + API
6. 迁移 Web 后端（FastAPI）→ 通过 Rust HTTP API 工作，删除直接文件访问
7. 添加 Auth (JWT)、CORS 配置、Rate limiting

### Phase 3 — 增强

1. Linux namespace 沙箱默认启用
2. WebSocket 推送替代 HTTP 轮询
3. Agent 流式响应（SSE/WebSocket）
4. 插件隔离执行
5. OpenTelemetry 可观测性
6. 性能优化：消息分页、任务批量处理

## 不做的范围（YAGNI）

- 不支持多进程 Rust Core（单进程 tokio runtime，水平扩展通过启动多个实例 + 上层负载均衡）
- 不实现完整的事件溯源（代价过高，普通 SQLite 表足够）
- 不替换 React 前端（仅在后端重构，前端通过 API 适配）
- 不引入 Kubernetes/容器编排（保持纯进程级管理）
