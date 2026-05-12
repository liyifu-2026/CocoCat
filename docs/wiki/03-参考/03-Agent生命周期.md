---
title: Agent 生命周期
sidebar_position: 3
---

# Agent 生命周期

## 状态机

```
        ┌──────────┐
        │  Disabled │ (config 中 enabled = false)
        └────┬─────┘
             │
        ┌────▼─────┐   spawn()    ┌───────────┐
        │  Loading  │ ──────────→ │  Running   │
        └──────────┘              └─────┬─────┘
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                         try_wait()=None    try_wait()=Some(ExitStatus)
                              │                   │
                         ┌────┴────┐        ┌─────▼──────┐
                         │ Running │        │   Dead     │
                         └─────────┘        └─────┬──────┘
                                                  │ restart_one()
                                                  ▼
                                            ┌───────────┐
                                            │  Spawning  │
                                            └─────┬─────┘
                                                  │
                                            ┌─────▼─────┐
                                            │  Running   │
                                            └───────────┘
```

## 完整流程

### 1. 启动

```
Rust main():
  1. 创建目录: chat/, agents/dispatch_queue/, agents/dispatch_messages/
  2. 初始化消息计数器
  3. AgentRegistry::load_config("agents/config.toml") → Vec<AgentConfig>
  4. registry.start_all():
     for each enabled agent:
       spawn("python", "py-agent/agent_runtime.py",
             ["--id", id, "--name", name, "--scene", scene])
```

**Spawn 参数**: `python -u py-agent/agent_runtime.py --id leader --name 组长 --scene development`

### 2. Agent 初始化

```
agent_runtime.py main():
  1. 解析 --id, --name, --scene → IDENTITY
  2. 启动心跳线程 (start_heartbeat, 300s 周期)
  3. 进入 stdin 循环:
     for line in sys.stdin:
       json.loads → handle_request()
       首次收到 task 请求时初始化 AgentRunner + AgentLoop
```

### 3. JSON-RPC 通信

Rust 通过 `transport.rs` 发送 JSON 行到 agent stdin,agent 从 stdout 返回 JSON 行。

```
请求:  {"jsonrpc":"2.0","method":"ping","id":1}
       {"jsonrpc":"2.0","method":"task","params":{"prompt":"..."},"id":2}

响应:  {"jsonrpc":"2.0","result":{"pong":true},"id":1}
       {"jsonrpc":"2.0","result":{"content":"...","iterations":3},"id":2}

错误:  {"jsonrpc":"2.0","error":{"code":-32603,"message":"..."},"id":2}
```

### 4. 健康检查

```
main.rs daemon loop:
  every 15s:
    for each running agent:
      agent.is_running() → child.try_wait()
        Ok(None) → 正常运行
        Ok(Some(_)) → 已退出,需要重启
        Err(_) → 需要重启

    重启流程:
      remove_dead(id) → 从 HashMap 移除
      restart_one(id) → 找 config → start_one() → spawn 新进程
```

### 5. Task 处理

Agent 收到 `task` 请求后:

```
handle_request("task"):
  1. AgentLoop.run(prompt)
  2. 构建 system prompt (上下文、记忆、工具描述、知识库概览)
  3. ReAct 循环:
     while iteration < max_iterations:
       LLM.chat(messages, tools)
       if tool_calls:
         并行执行工具 (ThreadPoolExecutor)
         结果追加到 messages
         consolidate() 压缩历史
         continue
       else:
         break
  4. append_history() + auto_dream()
  5. 返回 {"content": "...", "iterations": N}
```

### 6. 崩溃与重启

```
Agent 进程崩溃:
  → Rust try_wait() 检测到子进程退出
  → remove_dead("leader")
  → restart_one("leader")
  → spawn 新进程

无限重启: Rust 会持续尝试重启,直到 daemon 退出。
```

### 7. 关闭

```
main.rs 收到 "quit" / "exit" / Ctrl+C:
  → running.store(false)
  → AgentRegistry 析构:
    → drop(AgentProcess):
      → drop(stdin_writer)
      → child.kill()
      → child.wait()
  → 持久化消息计数器
  → 退出
```
