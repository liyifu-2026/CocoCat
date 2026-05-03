---
title: Rust 核心模块
sidebar_position: 7
---

# Rust 核心模块

```
src/
├── main.rs              # 入口,守护进程循环
├── lib.rs               # 模块声明
├── agent_manager.rs     # AgentProcess: 子进程封装
├── agent_registry.rs    # AgentRegistry: 配置加载 + 生命周期管理
├── message_bus.rs       # 聊天消息总线(持久化)
└── transport.rs         # JSON-RPC 2.0 线协议
```

## `main.rs` — 入口 + 守护进程

**核心流程**:

1. 创建目录: `chat/`, `agents/dispatch_queue/`, `agents/dispatch_messages/`
2. 初始化消息计数器 (`message_bus::init_counter()`)
3. 加载 agent 配置 (`AgentRegistry::load_config`)
4. 启动所有 agent (`registry.start_all()`)
5. 初始健康检查 (ping 每个 agent)
6. 初始身份识别 (identify 每个 agent)
7. 发送 Demo 任务给 leader (触发 dispatch 测试)
8. 进入守护循环:
   - 每 15s 健康检查 (`registry.health_check()`)
   - 每 5s 检查 dispatch queue (`check_and_process_dispatches()`)
   - 每 5s 检查 pending hires (`process_pending_hires()`)
   - 每 5s 检查 approved hires (`process_hire_requests()`)
   - 每 5s 检查用户提问 (`check_user_questions()`)
   - 持久化消息计数器

**Hire 处理** (`process_hire_requests`):
- 读取 `agents/hire_requests/approved/*.json`
- 追加 `[[agents]]` 条目到 `config.toml`
- 创建 memory 目录和 profile.json
- 调用 `registry.start_one()` 直接 spawn
- 日志写入消息总线

**Dispatch 处理** (`check_and_process_dispatches`):
- 读取 `agents/dispatch_queue/*.json`
- 解析 `target_id` → 调用 `registry.dispatch_message()`
- 通过 JSON-RPC 转发给目标 agent
- 响应写回消息总线
- 删除已处理的 dispatch 文件

## `agent_manager.rs` — AgentProcess

```rust
pub struct AgentProcess {
    child: Child,
    stdin_writer: Option<ChildStdin>,
    stdout_reader: BufReader<ChildStdout>,
    interpreter: String,
}
```

| 方法 | 说明 |
|------|------|
| `spawn(interpreter, script, args)` | 创建子进程,pipe stdin/stdout |
| `call(method, params, id)` | 发送 JSON-RPC 请求并读取响应 |
| `is_running()` | 调用 `child.try_wait()`,非阻塞检查 |
| `kill()` | 终止子进程 |
| `wait()` | 关闭 stdin,等待子进程退出 |

**Drop**: 自动关闭 stdin,杀掉并等待子进程。

## `agent_registry.rs` — AgentRegistry

```rust
pub struct AgentRegistry {
    pub configs: Vec<AgentConfig>,
    pub processes: HashMap<String, AgentProcess>,
}
```

| 方法 | 说明 |
|------|------|
| `load_config(path)` | 读取 TOML,解析 `Vec<AgentConfig>` |
| `new(configs)` | 创建 registry(不 spawn) |
| `start_all()` | spawn 所有 enabled agent |
| `start_one(config)` | spawn 单个 agent |
| `get(id)` | 通过 id 获取可变引用 |
| `status()` | 返回所有 agent 状态(含 running 标志) |
| `stop_all()` | 清空 processes map |
| `restart_one(id)` | 移除旧进程,根据 config 重新 spawn |
| `health_check()` | 遍历检查所有进程,重启已死进程 |
| `dispatch_message(id, method, params)` | JSON-RPC 调用 + 写 .msg 日志 |

## `transport.rs` — JSON-RPC 2.0 线协议

```rust
pub struct JsonRpcRequest {
    pub jsonrpc: String,    // "2.0"
    pub method: String,
    pub params: Option<Value>,
    pub id: u64,
}

pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub result: Option<Value>,
    pub error: Option<JsonRpcError>,
    pub id: Option<u64>,
}
```

**协议格式**: 单行 JSON, `\n` 分隔。

| 函数 | 说明 |
|------|------|
| `send_request(writer, req)` | 序列化 + writeln + flush |
| `read_response(reader)` | read_line + 反序列化 |

## `message_bus.rs` — 消息总线

```rust
pub struct ChatMessage {
    pub msg_id: String,         // "msg_000001"
    pub task_id: Option<u64>,
    pub timestamp: String,      // RFC 3339
    pub from: String,
    pub to: String,
    pub content: String,
    pub message_type: String,   // "system" | "task" | "reply"
}
```

| 函数 | 说明 |
|------|------|
| `log_message(msg)` | 原子写入 `chat/group.jsonl` (tmp + rename) |
| `read_recent(n)` | 读取最近 N 条消息 |
| `new_message(from, to, content, type)` | 创建自动编号的消息 |
| `init_counter()` | 从 `chat/.counter` 加载计数器 |
| `get_and_persist_counter()` | 保存计数器到磁盘 |
