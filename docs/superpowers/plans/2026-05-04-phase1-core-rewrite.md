# Phase 1: 最小可运行核心 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个能启动、接受消息、通过 JSON-RPC 调用 Python Agent 并返回结果的 async Rust 核心

**Architecture:** 单 tokio async 进程，SQLite (rusqlite + r2d2) 作为唯一状态存储，Python Agent 作为无状态子进程通过 stdin/stdout JSON-RPC 通信，axum HTTP server 对外暴露 API

**Tech Stack:** Rust (tokio, axum, rusqlite, r2d2, serde, tracing), Python (agent_loop.py 保持不变，agent_runtime.py 移除文件 I/O)

**工作目录:** `cocoact/.worktrees/rewrite-v2/`（worktree，分支 `rewrite-v2`）

---

## 文件结构

```
Cargo.toml                          # 修改：添加新依赖
src/
├── main.rs                         # 创建：tokio async 入口
├── lib.rs                          # 创建：模块重新导出
├── db/
│   ├── mod.rs                      # 创建：数据库模块
│   ├── pool.rs                     # 创建：SQLite 连接池 + WAL
│   ├── models.rs                   # 创建：Rust 结构体定义
│   ├── agents.rs                   # 创建：agents 表 CRUD
│   ├── messages.rs                 # 创建：messages 表 CRUD
│   └── tasks.rs                    # 创建：tasks 表 CRUD
├── agent/
│   ├── mod.rs                      # 创建：agent 模块
│   ├── process.rs                  # 创建：AgentProcess（JSON-RPC over stdio）
│   └── manager.rs                  # 创建：AgentManager（健康检查 / 重启）
├── dispatch/
│   ├── mod.rs                      # 创建：dispatch 模块
│   └── engine.rs                   # 创建：DispatchEngine（任务调度）
├── api/
│   ├── mod.rs                      # 创建：api 模块
│   ├── router.rs                   # 创建：axum 路由注册
│   └── chat.rs                     # 创建：POST /api/chat 处理器
py-agent/
├── agent_runtime.py                # 修改：移除文件 I/O，接受参数化配置
├── agent_loop.py                   # 不变（已干净）
├── llm.py                          # 不变
├── tools.py                        # 不变
└── sandbox.py                      # 不变
```

---

### Task 1: 项目脚手架 + 依赖

**Files:**
- Modify: `Cargo.toml`
- Create: `src/main.rs`
- Create: `src/lib.rs`

- [ ] **Step 1: 更新 Cargo.toml，添加新依赖**

```toml
[package]
name = "cococat"
version = "0.2.0"
edition = "2021"

[[bin]]
name = "cococat"
path = "src/main.rs"

[[bin]]
name = "cococat-legacy"
path = "src/bin/legacy_main.rs"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
chrono = { version = "0.4", features = ["serde"] }
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
tokio = { version = "1", features = ["full"] }
axum = "0.7"
rusqlite = { version = "0.31", features = ["bundled"] }
tokio-util = "0.7"
r2d2 = "0.8"
r2d2_sqlite = "0.24"
uuid = { version = "1", features = ["v4"] }
```

- [ ] **Step 2: 创建 src/main.rs**

```rust
use std::sync::Arc;
use tracing_subscriber::EnvFilter;

mod agent;
mod api;
mod db;
mod dispatch;
mod lib;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    tracing::info!("CocoCat v2 starting...");

    let db_pool = db::pool::create_pool()?;
    db::pool::run_migrations(&db_pool)?;

    let agents = db::agents::load_agents(&db_pool)?;
    tracing::info!("Loaded {} agents", agents.len());

    let agent_manager = Arc::new(agent::manager::AgentManager::new(db_pool.clone()));
    for agent_config in &agents {
        agent_manager.spawn(agent_config).await;
    }

    let (task_tx, task_rx) = tokio::sync::mpsc::channel::<dispatch::engine::TaskEvent>(256);
    let mut dispatch_engine = dispatch::engine::DispatchEngine::new(
        db_pool.clone(),
        agent_manager.clone(),
        task_rx,
    );

    let app_state = api::router::AppState {
        db_pool: db_pool.clone(),
        task_tx: task_tx.clone(),
    };
    let router = api::router::build(app_state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await?;
    tracing::info!("API server listening on :3000");

    tokio::select! {
        _ = dispatch_engine.run() => {
            tracing::warn!("Dispatch engine stopped");
        }
        _ = axum::serve(listener, router) => {
            tracing::warn!("HTTP server stopped");
        }
        _ = tokio::signal::ctrl_c() => {
            tracing::info!("Received SIGINT, shutting down...");
        }
    }

    tracing::info!("Shutdown complete");
    Ok(())
}
```

- [ ] **Step 3: 创建 src/lib.rs**

```rust
// Module re-exports. Each module is documented in its own file.
```

- [ ] **Step 4: 验证编译**

Run: `cd /home/leaif/CocoCat/.worktrees/rewrite-v2 && cargo check 2>&1`
Expected: 编译错误（因为模块尚未实现），确认新依赖下载成功

- [ ] **Step 5: Commit**

```bash
git add Cargo.toml src/main.rs src/lib.rs
git commit -m "feat: scaffold async Rust project with tokio + axum"
```

---

### Task 2: 数据库层 — 连接池 + 模型

**Files:**
- Create: `src/db/mod.rs`
- Create: `src/db/pool.rs`
- Create: `src/db/models.rs`

- [ ] **Step 1: 创建 src/db/mod.rs**

```rust
pub mod agents;
pub mod messages;
pub mod models;
pub mod pool;
pub mod tasks;
```

- [ ] **Step 2: 创建 src/db/pool.rs**

```rust
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use rusqlite::params;

pub type DbPool = Pool<SqliteConnectionManager>;

pub fn create_pool() -> Result<DbPool, Box<dyn std::error::Error>> {
    let manager = SqliteConnectionManager::file("cococat.db");
    let pool = Pool::builder()
        .max_size(8)
        .build(manager)?;

    // Enable WAL mode
    let conn = pool.get()?;
    conn.execute_batch(
        "PRAGMA journal_mode=WAL;
         PRAGMA foreign_keys=ON;
         PRAGMA busy_timeout=5000;"
    )?;

    Ok(pool)
}

pub fn run_migrations(pool: &DbPool) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT NOT NULL,
            scene_id TEXT NOT NULL DEFAULT 'default',
            status TEXT NOT NULL DEFAULT 'stopped'
                CHECK (status IN ('stopped','running','error')),
            system_prompt TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_heartbeat_at TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_uuid TEXT UNIQUE NOT NULL,
            agent_id TEXT REFERENCES agents(id),
            user_id TEXT,
            role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
            content TEXT NOT NULL,
            scene_id TEXT NOT NULL DEFAULT 'default',
            chat_group TEXT NOT NULL DEFAULT 'general',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_messages_scene_group
            ON messages(scene_id, chat_group, created_at);

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_uuid TEXT UNIQUE NOT NULL,
            target_agent TEXT NOT NULL REFERENCES agents(id),
            source TEXT NOT NULL,
            method TEXT NOT NULL,
            params TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','running','completed','failed','cancelled')),
            result TEXT,
            error TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            started_at TEXT,
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status_target
            ON tasks(status, target_agent)
            WHERE status IN ('pending','running');"
    )?;
    Ok(())
}

#[cfg(test)]
pub fn create_test_pool() -> DbPool {
    let manager = SqliteConnectionManager::memory();
    let pool = Pool::builder()
        .max_size(2)
        .build(manager)
        .expect("failed to create test pool");
    run_migrations(&pool).expect("test migration failed");
    pool
}
```

- [ ] **Step 3: 创建 src/db/models.rs**

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    pub id: String,
    pub name: String,
    pub role: String,
    pub model: String,
    pub scene_id: String,
    pub status: String,
    pub system_prompt: String,
    pub metadata: String,
    pub created_at: String,
    pub last_heartbeat_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub id: i64,
    pub msg_uuid: String,
    pub agent_id: Option<String>,
    pub user_id: Option<String>,
    pub role: String,
    pub content: String,
    pub scene_id: String,
    pub chat_group: String,
    pub metadata: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: i64,
    pub task_uuid: String,
    pub target_agent: String,
    pub source: String,
    pub method: String,
    pub params: String,
    pub status: String,
    pub result: Option<String>,
    pub error: Option<String>,
    pub retry_count: i32,
    pub max_retries: i32,
    pub created_at: String,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewMessage {
    pub msg_uuid: String,
    pub agent_id: Option<String>,
    pub user_id: Option<String>,
    pub role: String,
    pub content: String,
    pub scene_id: String,
    pub chat_group: String,
    pub metadata: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewTask {
    pub task_uuid: String,
    pub target_agent: String,
    pub source: String,
    pub method: String,
    pub params: String,
}
```

- [ ] **Step 4: 编译验证**

Run: `cargo check 2>&1`
Expected: 编译通过（模块空文件不会报错，因为没有被引用）

- [ ] **Step 5: Commit**

```bash
git add src/db/
git commit -m "feat: add SQLite pool, migrations, and data models"
```

---

### Task 3: 数据库层 — CRUD 操作

**Files:**
- Create: `src/db/agents.rs`
- Create: `src/db/messages.rs`
- Create: `src/db/tasks.rs`

- [ ] **Step 1: 创建 src/db/agents.rs**

```rust
use crate::db::models::Agent;
use crate::db::pool::DbPool;
use rusqlite::params;

pub fn load_agents(pool: &DbPool) -> Result<Vec<Agent>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, role, model, scene_id, status,
                system_prompt, metadata, created_at, last_heartbeat_at
         FROM agents WHERE status != 'stopped'"
    )?;

    let agents = stmt.query_map([], |row| {
        Ok(Agent {
            id: row.get(0)?,
            name: row.get(1)?,
            role: row.get(2)?,
            model: row.get(3)?,
            scene_id: row.get(4)?,
            status: row.get(5)?,
            system_prompt: row.get(6)?,
            metadata: row.get(7)?,
            created_at: row.get(8)?,
            last_heartbeat_at: row.get(9)?,
        })
    })?
    .filter_map(|r| r.ok())
    .collect();

    Ok(agents)
}

pub fn update_status(
    pool: &DbPool,
    agent_id: &str,
    status: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE agents SET status = ?1, last_heartbeat_at = datetime('now') WHERE id = ?2",
        params![status, agent_id],
    )?;
    Ok(())
}

pub fn get_agent(pool: &DbPool, agent_id: &str) -> Result<Option<Agent>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, role, model, scene_id, status,
                system_prompt, metadata, created_at, last_heartbeat_at
         FROM agents WHERE id = ?1"
    )?;

    let mut rows = stmt.query_map(params![agent_id], |row| {
        Ok(Agent {
            id: row.get(0)?,
            name: row.get(1)?,
            role: row.get(2)?,
            model: row.get(3)?,
            scene_id: row.get(4)?,
            status: row.get(5)?,
            system_prompt: row.get(6)?,
            metadata: row.get(7)?,
            created_at: row.get(8)?,
            last_heartbeat_at: row.get(9)?,
        })
    })?;

    Ok(rows.next().and_then(|r| r.ok()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::pool::create_test_pool;

    #[test]
    fn test_load_agents_empty() {
        let pool = create_test_pool();
        let agents = load_agents(&pool).unwrap();
        assert!(agents.is_empty());
    }

    #[test]
    fn test_update_status() {
        let pool = create_test_pool();
        let conn = pool.get().unwrap();
        conn.execute(
            "INSERT INTO agents (id, name, role, model, status) VALUES (?1, ?2, ?3, ?4, ?5)",
            params!["test_agent", "Test", "worker", "gpt-4", "stopped"],
        ).unwrap();
        drop(conn);

        update_status(&pool, "test_agent", "running").unwrap();

        let agent = get_agent(&pool, "test_agent").unwrap().unwrap();
        assert_eq!(agent.status, "running");
    }
}
```

- [ ] **Step 2: 创建 src/db/messages.rs**

```rust
use crate::db::models::{Message, NewMessage};
use crate::db::pool::DbPool;
use rusqlite::params;

pub fn insert_message(
    pool: &DbPool,
    msg: &NewMessage,
) -> Result<Message, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, chat_group, metadata)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            msg.msg_uuid,
            msg.agent_id,
            msg.user_id,
            msg.role,
            msg.content,
            msg.scene_id,
            msg.chat_group,
            msg.metadata,
        ],
    )?;

    let id = conn.last_insert_rowid();
    let mut stmt = conn.prepare(
        "SELECT id, msg_uuid, agent_id, user_id, role, content,
                scene_id, chat_group, metadata, created_at
         FROM messages WHERE id = ?1"
    )?;

    Ok(stmt.query_row(params![id], |row| {
        Ok(Message {
            id: row.get(0)?,
            msg_uuid: row.get(1)?,
            agent_id: row.get(2)?,
            user_id: row.get(3)?,
            role: row.get(4)?,
            content: row.get(5)?,
            scene_id: row.get(6)?,
            chat_group: row.get(7)?,
            metadata: row.get(8)?,
            created_at: row.get(9)?,
        })
    })?)
}

pub fn get_recent_messages(
    pool: &DbPool,
    scene_id: &str,
    chat_group: &str,
    limit: i64,
) -> Result<Vec<Message>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, msg_uuid, agent_id, user_id, role, content,
                scene_id, chat_group, metadata, created_at
         FROM messages
         WHERE scene_id = ?1 AND chat_group = ?2
         ORDER BY created_at DESC
         LIMIT ?3"
    )?;

    let messages = stmt
        .query_map(params![scene_id, chat_group, limit], |row| {
            Ok(Message {
                id: row.get(0)?,
                msg_uuid: row.get(1)?,
                agent_id: row.get(2)?,
                user_id: row.get(3)?,
                role: row.get(4)?,
                content: row.get(5)?,
                scene_id: row.get(6)?,
                chat_group: row.get(7)?,
                metadata: row.get(8)?,
                created_at: row.get(9)?,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

    Ok(messages)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::pool::create_test_pool;

    #[test]
    fn test_insert_and_query_message() {
        let pool = create_test_pool();
        let msg = NewMessage {
            msg_uuid: "test-uuid-1".into(),
            agent_id: None,
            user_id: Some("user1".into()),
            role: "user".into(),
            content: "Hello".into(),
            scene_id: "default".into(),
            chat_group: "general".into(),
            metadata: "{}".into(),
        };

        let saved = insert_message(&pool, &msg).unwrap();
        assert_eq!(saved.content, "Hello");
        assert_eq!(saved.role, "user");

        let recent = get_recent_messages(&pool, "default", "general", 10).unwrap();
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].content, "Hello");
    }
}
```

- [ ] **Step 3: 创建 src/db/tasks.rs**

```rust
use crate::db::models::{NewTask, Task};
use crate::db::pool::DbPool;
use rusqlite::params;

pub fn create_task(
    pool: &DbPool,
    task: &NewTask,
) -> Result<Task, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO tasks (task_uuid, target_agent, source, method, params, status)
         VALUES (?1, ?2, ?3, ?4, ?5, 'pending')",
        params![
            task.task_uuid,
            task.target_agent,
            task.source,
            task.method,
            task.params,
        ],
    )?;

    let id = conn.last_insert_rowid();
    let mut stmt = conn.prepare(
        "SELECT id, task_uuid, target_agent, source, method, params, status,
                result, error, retry_count, max_retries, created_at, started_at, completed_at
         FROM tasks WHERE id = ?1"
    )?;

    Ok(stmt.query_row(params![id], |row| {
        Ok(Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            created_at: row.get(11)?,
            started_at: row.get(12)?,
            completed_at: row.get(13)?,
        })
    })?)
}

pub fn claim_pending_task(
    pool: &DbPool,
) -> Result<Option<Task>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "UPDATE tasks SET status = 'running', started_at = datetime('now')
         WHERE task_uuid = (
             SELECT task_uuid FROM tasks
             WHERE status = 'pending'
             ORDER BY created_at ASC
             LIMIT 1
         )
         RETURNING id, task_uuid, target_agent, source, method, params, status,
                   result, error, retry_count, max_retries, created_at, started_at, completed_at"
    )?;

    let result = stmt.query_row([], |row| {
        Ok(Task {
            id: row.get(0)?,
            task_uuid: row.get(1)?,
            target_agent: row.get(2)?,
            source: row.get(3)?,
            method: row.get(4)?,
            params: row.get(5)?,
            status: row.get(6)?,
            result: row.get(7)?,
            error: row.get(8)?,
            retry_count: row.get(9)?,
            max_retries: row.get(10)?,
            created_at: row.get(11)?,
            started_at: row.get(12)?,
            completed_at: row.get(13)?,
        })
    });

    match result {
        Ok(task) => Ok(Some(task)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.into()),
    }
}

pub fn complete_task(
    pool: &DbPool,
    task_uuid: &str,
    result: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE tasks SET status = 'completed', result = ?1, completed_at = datetime('now')
         WHERE task_uuid = ?2",
        params![result, task_uuid],
    )?;
    Ok(())
}

pub fn fail_task(
    pool: &DbPool,
    task_uuid: &str,
    error: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE tasks SET status = 'failed', error = ?1, completed_at = datetime('now')
         WHERE task_uuid = ?2",
        params![error, task_uuid],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::pool::create_test_pool;

    #[test]
    fn test_create_and_claim_task() {
        let pool = create_test_pool();
        let task = NewTask {
            task_uuid: "task-1".into(),
            target_agent: "leader".into(),
            source: "test".into(),
            method: "chat".into(),
            params: "{}".into(),
        };

        create_task(&pool, &task).unwrap();
        let claimed = claim_pending_task(&pool).unwrap().unwrap();
        assert_eq!(claimed.task_uuid, "task-1");
        assert_eq!(claimed.status, "running");

        // Second claim should return None
        assert!(claim_pending_task(&pool).unwrap().is_none());
    }

    #[test]
    fn test_complete_and_fail() {
        let pool = create_test_pool();
        let task = NewTask {
            task_uuid: "task-2".into(),
            target_agent: "leader".into(),
            source: "test".into(),
            method: "chat".into(),
            params: "{}".into(),
        };

        create_task(&pool, &task).unwrap();
        let claimed = claim_pending_task(&pool).unwrap().unwrap();

        complete_task(&pool, &claimed.task_uuid, r#"{"response":"ok"}"#).unwrap();

        let conn = pool.get().unwrap();
        let result: String = conn.query_row(
            "SELECT result FROM tasks WHERE task_uuid = ?1",
            params!["task-2"],
            |row| row.get(0),
        ).unwrap();
        assert_eq!(result, r#"{"response":"ok"}"#);
    }
}
```

- [ ] **Step 4: 运行测试**

Run: `cargo test db:: -- --nocapture 2>&1`
Expected: 所有数据库测试通过

- [ ] **Step 5: Commit**

```bash
git add src/db/agents.rs src/db/messages.rs src/db/tasks.rs
git commit -m "feat: implement DB CRUD for agents, messages, tasks"
```

---

### Task 4: Agent 进程管理

**Files:**
- Create: `src/agent/mod.rs`
- Create: `src/agent/process.rs`
- Create: `src/agent/manager.rs`

- [ ] **Step 1: 创建 src/agent/mod.rs**

```rust
pub mod manager;
pub mod process;
```

- [ ] **Step 2: 创建 src/agent/process.rs**

```rust
use crate::db::models::Agent;
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

pub struct AgentProcess {
    pub agent_id: String,
    child: Child,
    stdin_writer: Option<ChildStdin>,
    stderr_output: String,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: String,
    pub method: String,
    pub params: Value,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct JsonRpcError {
    pub code: i64,
    pub message: String,
}

impl AgentProcess {
    pub fn spawn(config: &Agent) -> Result<Self, String> {
        let mut child = Command::new("python")
            .arg("-u")
            .arg("py-agent/agent_runtime.py")
            .arg("--agent-id")
            .arg(&config.id)
            .arg("--model")
            .arg(&config.model)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn agent {}: {}", config.id, e))?;

        let stdin_writer = child.stdin.take()
            .ok_or_else(|| "Failed to take stdin".to_string())?;
        let stderr = child.stderr.take()
            .ok_or_else(|| "Failed to take stderr".to_string())?;

        // Read stderr in a background thread
        let stderr_output = String::new();
        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                if let Ok(line) = line {
                    eprintln!("[{}:stderr] {}", config.id, line);
                }
            }
        });

        Ok(Self {
            agent_id: config.id.clone(),
            child,
            stdin_writer: Some(stdin_writer),
            stderr_output,
        })
    }

    pub fn call(
        &mut self,
        method: &str,
        params: Value,
        timeout_secs: u64,
    ) -> Result<Value, String> {
        let stdout = self.child.stdout.take()
            .ok_or_else(|| "stdout already taken".to_string())?;

        let request = JsonRpcRequest {
            jsonrpc: "2.0".into(),
            id: uuid::Uuid::new_v4().to_string(),
            method: method.into(),
            params,
        };

        let request_line = serde_json::to_string(&request)
            .map_err(|e| format!("serialize request: {}", e))?;

        if let Some(ref mut stdin) = self.stdin_writer {
            writeln!(stdin, "{}", request_line)
                .map_err(|e| format!("write to stdin: {}", e))?;
            stdin.flush().map_err(|e| format!("flush stdin: {}", e))?;
        } else {
            return Err("stdin closed".to_string());
        }

        let (tx, rx) = mpsc::channel();
        let mut reader = BufReader::new(stdout);

        thread::spawn(move || {
            let mut line = String::new();
            let result = reader.read_line(&mut line);
            let _ = tx.send((line, result.map_err(|e| e.to_string())));
        });

        let (line, read_result) = if timeout_secs > 0 {
            match rx.recv_timeout(Duration::from_secs(timeout_secs)) {
                Ok(result) => result,
                Err(mpsc::RecvTimeoutError::Timeout) => {
                    let _ = self.child.kill();
                    return Err(format!("Agent {} call timed out after {}s", self.agent_id, timeout_secs));
                }
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    return Err("Agent stdout channel disconnected".to_string());
                }
            }
        } else {
            rx.recv().map_err(|_| "Agent stdout channel disconnected".to_string())?
        };

        read_result?;

        let response: JsonRpcResponse = serde_json::from_str(&line)
            .map_err(|e| format!("parse JSON-RPC response: {} (raw: {})", e, line))?;

        if let Some(err) = response.error {
            return Err(format!("Agent error: {} (code {})", err.message, err.code));
        }

        Ok(response.result.unwrap_or(Value::Null))
    }

    pub fn is_running(&mut self) -> bool {
        match self.child.try_wait() {
            Ok(Some(_)) => false,
            _ => true,
        }
    }

    pub fn kill(&mut self) -> Result<(), String> {
        let _ = self.stdin_writer.take();
        self.child.kill().map_err(|e| format!("kill agent: {}", e))?;
        let _ = self.child.wait();
        Ok(())
    }
}

impl Drop for AgentProcess {
    fn drop(&mut self) {
        let _ = self.stdin_writer.take();
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
```

- [ ] **Step 3: 创建 src/agent/manager.rs**

```rust
use crate::agent::process::AgentProcess;
use crate::db::models::Agent;
use crate::db::pool::DbPool;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::Duration;

pub struct AgentManager {
    db_pool: DbPool,
    processes: Arc<Mutex<HashMap<String, AgentProcess>>>,
}

impl AgentManager {
    pub fn new(db_pool: DbPool) -> Self {
        Self {
            db_pool,
            processes: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub async fn spawn(&self, config: &Agent) {
        let process = match AgentProcess::spawn(config) {
            Ok(p) => p,
            Err(e) => {
                tracing::error!("Failed to spawn agent {}: {}", config.id, e);
                return;
            }
        };

        let mut processes = self.processes.lock().unwrap();
        processes.insert(config.id.clone(), process);
        tracing::info!("Agent {} spawned", config.id);

        // Update DB status
        let _ = crate::db::agents::update_status(&self.db_pool, &config.id, "running");
    }

    pub fn call_agent(
        &self,
        agent_id: &str,
        method: &str,
        params: serde_json::Value,
        timeout_secs: u64,
    ) -> Result<serde_json::Value, String> {
        let mut processes = self.processes.lock().map_err(|e| format!("lock: {}", e))?;
        let process = processes.get_mut(agent_id)
            .ok_or_else(|| format!("Agent {} not found", agent_id))?;
        process.call(method, params, timeout_secs)
    }

    pub async fn health_check_loop(self: Arc<Self>) {
        loop {
            tokio::time::sleep(Duration::from_secs(15)).await;

            let dead_agents: Vec<String> = {
                let mut processes = match self.processes.lock() {
                    Ok(p) => p,
                    Err(_) => continue,
                };
                processes
                    .iter_mut()
                    .filter(|(_, p)| !p.is_running())
                    .map(|(id, _)| id.clone())
                    .collect()
            };

            for id in &dead_agents {
                tracing::warn!("Agent {} is dead, removing", id);
                let _ = self.processes.lock().map(|mut p| p.remove(id));
                let _ = crate::db::agents::update_status(&self.db_pool, id, "error");
            }
        }
    }
}
```

- [ ] **Step 4: 编译验证**

Run: `cargo check 2>&1`
Expected: 编译通过

- [ ] **Step 5: Commit**

```bash
git add src/agent/
git commit -m "feat: add agent process management with JSON-RPC over stdio"
```

---

### Task 5: 调度引擎

**Files:**
- Create: `src/dispatch/mod.rs`
- Create: `src/dispatch/engine.rs`

- [ ] **Step 1: 创建 src/dispatch/mod.rs**

```rust
pub mod engine;
```

- [ ] **Step 2: 创建 src/dispatch/engine.rs**

```rust
use crate::agent::manager::AgentManager;
use crate::db::pool::DbPool;
use crate::db::tasks;
use serde_json::Value;
use std::sync::Arc;
use tokio::sync::mpsc::Receiver;

#[derive(Debug, Clone)]
pub enum TaskEvent {
    NewTask { task_uuid: String },
    Shutdown,
}

pub struct DispatchEngine {
    db_pool: DbPool,
    agent_manager: Arc<AgentManager>,
    rx: Receiver<TaskEvent>,
}

impl DispatchEngine {
    pub fn new(
        db_pool: DbPool,
        agent_manager: Arc<AgentManager>,
        rx: Receiver<TaskEvent>,
    ) -> Self {
        Self {
            db_pool,
            agent_manager,
            rx,
        }
    }

    pub async fn run(&mut self) {
        tracing::info!("Dispatch engine started");

        loop {
            tokio::select! {
                Some(event) = self.rx.recv() => {
                    match event {
                        TaskEvent::NewTask { task_uuid } => {
                            if let Err(e) = self.process_task(&task_uuid) {
                                tracing::error!("Failed to process task {}: {}", task_uuid, e);
                            }
                        }
                        TaskEvent::Shutdown => {
                            tracing::info!("Dispatch engine shutting down");
                            break;
                        }
                    }
                }
                else => {
                    // Channel closed, exit
                    tracing::warn!("Task channel closed");
                    break;
                }
            }
        }
    }

    /// NOTE: agent_manager.call_agent is synchronous (std::sync::Mutex + blocking I/O).
    /// We use spawn_blocking to avoid blocking the tokio runtime.
    async fn process_task(&self, task_uuid: &str) -> Result<(), String> {
        // Claim the task
        let (task, agent_manager) = {
            let task = tasks::claim_pending_task(&self.db_pool)
                .map_err(|e| format!("claim task: {}", e))?
                .ok_or_else(|| format!("Task {} not found or already claimed", task_uuid))?;
            (task, self.agent_manager.clone())
        };

        let target = task.target_agent.clone();
        let method = task.method.clone();
        let params: Value = serde_json::from_str(&task.params)
            .map_err(|e| format!("parse params: {}", e))?;

        tracing::info!("Dispatching task {} to agent {}", task_uuid, target);

        let call_result = tokio::task::spawn_blocking(move || {
            agent_manager.call_agent(&target, &method, params, 120)
        }).await.map_err(|e| format!("join error: {}", e))?;

        match call_result {
            Ok(result) => {
                let result_str = serde_json::to_string(&result)
                    .map_err(|e| format!("serialize result: {}", e))?;
                tasks::complete_task(&self.db_pool, task_uuid, &result_str)
                    .map_err(|e| format!("complete task: {}", e))?;
                tracing::info!("Task {} completed successfully", task_uuid);
                Ok(())
            }
            Err(e) => {
                tracing::error!("Task {} failed: {}", task_uuid, e);
                tasks::fail_task(&self.db_pool, task_uuid, &e)
                    .map_err(|e2| format!("fail task: {}", e2))?;
                Err(e)
            }
        }
    }
}
```

- [ ] **Step 3: 编译验证**

Run: `cargo check 2>&1`
Expected: 编译通过

- [ ] **Step 4: Commit**

```bash
git add src/dispatch/
git commit -m "feat: add dispatch engine with task claiming and execution"
```

---

### Task 6: HTTP API

**Files:**
- Create: `src/api/mod.rs`
- Create: `src/api/router.rs`
- Create: `src/api/chat.rs`

- [ ] **Step 1: 创建 src/api/mod.rs**

```rust
pub mod chat;
pub mod router;
```

- [ ] **Step 2: 创建 src/api/router.rs**

```rust
use crate::db::pool::DbPool;
use axum::{routing::post, Router};
use tokio::sync::mpsc::Sender;
use std::sync::Arc;

use super::chat;

#[derive(Clone)]
pub struct AppState {
    pub db_pool: DbPool,
    pub task_tx: Sender<crate::dispatch::engine::TaskEvent>,
}

pub fn build(state: AppState) -> Router {
    Router::new()
        .route("/api/health", axum::routing::get(health))
        .route("/api/chat", post(chat::chat_handler))
        .with_state(state)
}

async fn health() -> &'static str {
    "OK"
}
```

- [ ] **Step 3: 创建 src/api/chat.rs**

```rust
use crate::db::models::NewMessage;
use crate::db::{messages, tasks};
use crate::dispatch::engine::TaskEvent;
use axum::{
    extract::State,
    Json,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use super::router::AppState;

#[derive(Deserialize)]
pub struct ChatRequest {
    pub content: String,
    pub agent_id: String,
    pub scene_id: Option<String>,
    pub user_id: Option<String>,
}

#[derive(Serialize)]
pub struct ChatResponse {
    pub msg_uuid: String,
    pub task_uuid: String,
    pub assistant_content: String,
}

pub async fn chat_handler(
    State(state): State<AppState>,
    Json(req): Json<ChatRequest>,
) -> Result<Json<ChatResponse>, axum::http::StatusCode> {
    let scene_id = req.scene_id.unwrap_or_else(|| "default".to_string());

    // 1. Save user message
    let user_msg_uuid = uuid::Uuid::new_v4().to_string();
    let user_msg = NewMessage {
        msg_uuid: user_msg_uuid.clone(),
        agent_id: None,
        user_id: req.user_id.clone(),
        role: "user".into(),
        content: req.content.clone(),
        scene_id: scene_id.clone(),
        chat_group: "general".into(),
        metadata: "{}".into(),
    };

    messages::insert_message(&state.db_pool, &user_msg)
        .map_err(|e| {
            tracing::error!("Failed to save user message: {}", e);
            axum::http::StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // 2. Create task
    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "content": req.content,
        "scene_id": scene_id,
    });

    let task = tasks::create_task(&state.db_pool, &crate::db::models::NewTask {
        task_uuid: task_uuid.clone(),
        target_agent: req.agent_id.clone(),
        source: "web".into(),
        method: "chat".into(),
        params: params.to_string(),
    }).map_err(|e| {
        tracing::error!("Failed to create task: {}", e);
        axum::http::StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // 3. Notify dispatch engine
    state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await.map_err(|e| {
        tracing::error!("Failed to notify dispatch engine: {}", e);
        axum::http::StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // For Phase 1, we return immediately and the dispatch engine
    // processes the task asynchronously.
    // Phase 2 will add polling or WebSocket for result delivery.
    Ok(Json(ChatResponse {
        msg_uuid: user_msg_uuid,
        task_uuid: task_uuid.clone(),
        assistant_content: "Task submitted. Result will be available shortly.".into(),
    }))
}
```

- [ ] **Step 4: 更新 src/main.rs 的 db 模块引用**

确保 `src/main.rs` 开头引用完整：
```rust
mod agent;
mod api;
mod db;
mod dispatch;
```

- [ ] **Step 5: 编译验证**

Run: `cargo check 2>&1`
Expected: 编译通过

- [ ] **Step 6: Commit**

```bash
git add src/api/
git commit -m "feat: add HTTP API with health and chat endpoints"
```

---

### Task 7: 修改 Python Agent 运行时

**Files:**
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: 读取当前 agent_runtime.py**

Run: `cat py-agent/agent_runtime.py`
Purpose: 理解当前代码结构以便修改

- [ ] **Step 2: 修改 agent_runtime.py 接受参数化配置**

当前的 `agent_runtime.py` 可能通过文件系统或环境变量读取配置。修改为接受命令行参数 `--agent-id` 和 `--model`，移除对 `agents/config.toml` 和 `agents/leader/` 等文件路径的硬编码依赖。

关键修改点：
1. 通过 `argparse` 接受 `--agent-id` 和 `--model` 参数
2. 系统提示词通过 JSON-RPC 的 `identify` 方法返回，不从文件读取
3. 心跳线程改为通过 JSON-RPC 通知 Rust 核心，而非写文件
4. `agent_loop.py` 的 `run()` 方法改为接受 `(messages, tools)` 参数而非从文件加载

```python
#!/usr/bin/env python3
"""Agent runtime - stdio JSON-RPC server for CocoCat v2."""
import argparse
import json
import sys
import traceback

from agent_loop import AgentLoop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--model", default="gpt-4")
    parser.add_argument("--system-prompt", default="")
    args = parser.parse_args()

    agent_loop = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            _send_error(None, -32700, f"Parse error: {e}")
            continue

        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            if method == "ping":
                _send_result(req_id, {"pong": True, "agent_id": args.agent_id})

            elif method == "identify":
                _send_result(req_id, {
                    "agent_id": args.agent_id,
                    "model": args.model,
                    "system_prompt": args.system_prompt,
                })

            elif method == "chat":
                if agent_loop is None:
                    from agent_runner import AgentRunner
                    agent_loop = AgentRunner(args.agent_id, args.model)

                content = params.get("content", "")
                messages = params.get("messages", [])
                result = agent_loop.run(content, messages)
                _send_result(req_id, {"response": result})

            elif method == "shutdown":
                _send_result(req_id, {"shutdown": True})
                break

            else:
                _send_error(req_id, -32601, f"Method not found: {method}")

        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            _send_error(req_id, -32603, str(e))


def _send_result(req_id, result):
    response = {"jsonrpc": "2.0", "id": req_id, "result": result}
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def _send_error(req_id, code, message):
    response = {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 修改 agent_runner.py**

`agent_runner.py` 的 `run()` 方法改为接受直接参数而非从文件系统加载上下文：

```python
"""AgentRunner facade for CocoCat v2."""
from agent_loop import AgentLoop


class AgentRunner:
    def __init__(self, agent_id: str, model: str):
        self.agent_id = agent_id
        self.model = model
        self.loop = AgentLoop(model=model)

    def run(self, user_content: str, history_messages: list | None = None) -> str:
        messages = list(history_messages or [])
        messages.append({"role": "user", "content": user_content})
        result = self.loop.run(messages)
        return result
```

- [ ] **Step 4: 修改 agent_loop.py**

`agent_loop.py` 的 `run()` 改为接受 `messages` 参数列表而非内部拼接：

```python
"""Minimal ReAct agent loop for CocoCat v2."""
from llm import LLMClient


class AgentLoop:
    def __init__(self, model: str = "gpt-4"):
        self.llm = LLMClient(model=model)

    def run(self, messages: list) -> str:
        # Simple single-turn for Phase 1
        # Phase 2 will add full ReAct loop with tool calling
        response = self.llm.chat(messages)
        return response
```

- [ ] **Step 5: 验证 Python 代码语法**

Run: `cd /home/leaif/CocoCat/.worktrees/rewrite-v2 && python -c "import ast; ast.parse(open('py-agent/agent_runtime.py').read()); print('OK')" 2>&1`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add py-agent/agent_runtime.py py-agent/agent_runner.py py-agent/agent_loop.py
git commit -m "refactor: make Python agent runtime stateless with CLI args"
```

---

### Task 8: 集成 E2E 测试

**Files:**
- Create: `tests/integration_test.rs`

- [ ] **Step 1: 创建集成测试框架**

```rust
// tests/integration_test.rs
// Integration test for Phase 1 core.
// Requires: a running cococat daemon or the ability to start one.

use std::process::{Command, Child};
use std::time::Duration;

struct CocoCatInstance {
    child: Child,
}

impl CocoCatInstance {
    fn start() -> Self {
        let child = Command::new("cargo")
            .args(["run", "--bin", "cococat"])
            .env("RUST_LOG", "debug")
            .spawn()
            .expect("Failed to start cococat");

        Self { child }
    }

    fn stop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Drop for CocoCatInstance {
    fn drop(&mut self) {
        self.stop();
    }
}

#[tokio::test]
async fn test_health_check() {
    let mut instance = CocoCatInstance::start();
    tokio::time::sleep(Duration::from_secs(3)).await; // Wait for startup

    let client = reqwest::Client::new();
    let resp = client.get("http://localhost:3000/api/health")
        .send()
        .await
        .expect("Health check failed");
    assert!(resp.status().is_success());
    let body = resp.text().await.unwrap();
    assert_eq!(body, "OK");
}
```

添加 `dev-dependencies` 到 `Cargo.toml`：
```toml
[dev-dependencies]
reqwest = { version = "0.12", features = ["json"] }
```

- [ ] **Step 2: 运行集成测试**

Run: `cargo test --test integration_test -- --nocapture 2>&1`
Expected: 测试通过，验证健康检查和基本启动流程

- [ ] **Step 3: Commit**

```bash
git add Cargo.toml tests/integration_test.rs
git commit -m "test: add integration test for daemon health check"
```

---

## 自检清单

1. **Spec coverage:** 设计文档中 Phase 1 的 7 项需求全部覆盖：项目骨架(Task1)、SQLite(Task2-3)、Agent 管理(Task4)、调度引擎(Task5)、HTTP API(Task6)、Python 运行时(Task7)、E2E 测试(Task8)
2. **Placeholder scan:** 无 TBD/TODO，每步含完整代码
3. **Type consistency:** `NewTask` -> `tasks::create_task` -> `claim_pending_task` -> `complete_task` 类型链一致；`AgentProcess::call` 参数类型与 `JsonRpcRequest/Response` 匹配
