---
title: 调试 Agent 行为
sidebar_position: 5
---

# 调试 Agent 行为

当 Agent 行为异常时，按以下层次逐步排查。

## 第一层：查看 Agent 日志

Agent 的 stdout/stderr 输出在 Rust 核心的控制台日志中。查看启动 Rust 核心的终端或日志文件：

```
[INFO] Agent leader spawned (pid: 12345)
[INFO] Health check: leader OK
[ERROR] Agent employee_a: LLM API error: 401 Unauthorized
```

常见日志前缀：
- `[INFO]` — 正常状态信息
- `[WARN]` — 异常但可恢复
- `[ERROR]` — 需要关注的错误

## 第二层：检查内存和记忆文件

### MEMORY.md

Agent 的长期记忆文件，位于 `agents/{id}/memory/MEMORY.md`。检查是否包含了不应有的信息，或缺少关键上下文。

```bash
cat agents/leader/memory/MEMORY.md
```

### history.jsonl

Agent 的任务执行历史记录：

```bash
tail -20 agents/leader/memory/history.jsonl
```

每条记录包含 `timestamp`、`prompt`、`response_summary`、`iterations`。

### Dream 游标

```bash
cat agents/leader/memory/.dream_cursor  # 当前处理到的历史位置
```

如果 Dream 卡住，可手动重置游标（设回 0 触重新处理）。

## 第三层：检查消息总线

### 聊天群组

所有消息记录在 `chat/group.jsonl`：

```bash
tail -50 chat/group.jsonl
```

检查消息是否被正确路由、是否重复、格式是否异常。

### Agent 邮箱

Agent 间通信通过邮箱系统，位于 `agents/mailbox/{id}/inbox.jsonl`：

```bash
tail -20 agents/mailbox/employee_a/inbox.jsonl
```

检查是否有未被消费的消息（`status: "unread"`）。

### Dispatch 队列

任务分发文件位于 `agents/dispatch_queue/`：

```bash
ls agents/dispatch_queue/
```

如果有残留文件（未被 Rust 消费），说明分发或路由出现问题。

## 第四层：使用 Web 面板

- **Agent 详情页**：查看 profile、skills、memory 内容
- **对话记录**：查看场景对话历史
- **系统状态**：查看各 Agent 运行状态
- **Token 用量**：排查是否因超预算导致截断

## 第五层：单 Agent 手动调试

启动单个 Agent 进程并手动发送 JSON-RPC 请求：

```bash
# 终端 1：启动 agent
python py-agent/agent_runtime.py --id debug --name Debug --scene default

# 终端 2：发送测试请求
echo '{"jsonrpc":"2.0","method":"task","params":{"prompt":"Hello"},"id":1}'
```

查看 agent 的 stdout 输出，确认 ReAct 循环是否正确执行。

## 排错速查表

| 症状 | 排查方向 |
|------|----------|
| Agent 不响应 | 检查健康检查日志 → 确认进程存活 | |
| Agent 返回空内容 | 检查 LLM API 错误 → 检查 `.env` 配置 → 检查网络 |
| Web 面板 401 | 检查 JWT_SECRET 一致性 → 检查 auth middleware |
| 文件权限错误 | 检查 PathValidator 配置 → 检查 COCOCAT_WORKSPACE |
| 工具调用失败 | 检查 tool execute 日志 → 检查参数格式 |
| Agent 间通信失败 | 检查 dispatch_queue 文件 → 检查 Rust 轮询 |
| Dream 不执行 | 检查 `.dream_cursor` → 检查 history.jsonl 行数 |
