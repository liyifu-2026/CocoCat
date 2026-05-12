---
title: 为什么 Rust + Python
sidebar_position: 1
---

# 为什么 Rust + Python

CocoCat 采用 Rust + Python 双语言架构，不是出于技术炫耀，而是**让每种语言做它最擅长的事**。

## 分工原则

| 层面 | 语言 | 职责 |
|------|------|------|
| 核心引擎 | Rust | Agent 生命周期、进程管理、消息路由、健康检查、守护循环 |
| Agent 运行时 | Python | LLM 调用、ReAct 循环、工具执行、记忆管理、知识库处理 |

## 为什么核心引擎用 Rust？

**Agent 核心引擎的需求**：

1. **长时间稳定运行** — 核心是守护进程，可能连续运行数周甚至数月。Rust 无 GC、无运行时，内存安全且可预测
2. **子进程管理** — 需要 spawn、监控、重启子进程。Rust 的 `std::process` 提供精确的进程控制
3. **非阻塞轮询** — 15s 健康检查 + 5s dispatch 轮询 + 5s hire 轮询。Rust 的 `try_wait()` 非阻塞检查完美匹配
4. **低资源占用** — 核心本身几乎不占用 CPU，把资源留给 Agent 进程。Rust 二进制小、内存占用低
5. **无依赖部署** — 编译为单二进制，无需安装 Python 运行时

**Rust 不擅长的**：LLM 调用、动态 schema 处理、快速迭代的实验性功能。这也是 Python 存在的原因。

## 为什么 Agent 运行时用 Python？

**Agent 运行时的需求**：

1. **LLM 生态** — OpenAI SDK、LangChain、tiktoken 等全部是 Python 生态。用 Rust 实现等价功能需要数倍工作量
2. **动态性** — Tool 的 schema、LLM 返回的 tool_calls 结构、system prompt 构建都需要频繁调整。Python 无需编译，改完即生效
3. **文本处理** — 正则、JSON 解析、Markdown 渲染、模板引擎。Python 的标准库和生态无可替代
4. **实验成本低** — Agent 行为调试=改 prompt + 重跑，Python 的迭代速度远快于 Rust 编译周期

**Python 不擅长的**：并发进程管理、低延迟 I/O 轮询、长时间运行的守护进程。这正是 Rust 的强项。

## 为什么不只用一种语言？

| 方案 | 问题 |
|------|------|
| 全部 Rust | LLM 生态缺失，开发效率低，Tool 实现繁琐 |
| 全部 Python | 进程管理脆弱，依赖 Python 运行时，资源开销大 |
| Rust 核心 + Python Agent | 各取所长，唯一的代价是 JSON-RPC 序列化开销（可忽略） |

## 通信代价

Rust 与 Python 通过 JSON-RPC over stdin/stdout 通信：

- 每次调用约 0.1ms 序列化/反序列化
- Agent 的 ReAct 循环通常 3-10 轮，每轮包含一次 LLM 调用（耗时 1-10s）
- JSON-RPC 开销占总时间的 **<0.01%**，可忽略不计

## 结论

Rust + Python 是一对经过实战验证的组合：Rust 提供**可靠性**骨架，Python 提供**灵活性**血肉。CocoCat 不是第一个这样做的项目（nanobot、Claude Code 等都采用了类似思路），也不会是最后一个。
