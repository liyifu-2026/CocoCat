---
title: 术语表
sidebar_position: 1
---

# 术语表

## A

### Agent
AI 智能体——一个有独立身份、记忆、技能和 LLM 配置的虚拟角色。每个 Agent 像一名虚拟员工，在团队中承担特定角色。

### AgentLoop
Agent 的核心执行引擎，实现 ReAct 循环。负责维护消息历史、调用 LLM、执行工具、管理 token 预算。

### AgentRunner
Agent 的外观类（Facade），封装了 AgentLoop 的初始化和运行逻辑。负责加载场景上下文、创建 ToolRegistry、管理缓存。

## C

### Channel（频道）
Agent 与外部用户交互的渠道抽象。支持微信、飞书、Web API 等。每个 Channel 实现 `start()` 和 `send()` 方法。

### Consolidator
ReAct 循环中的历史压缩机制。当消息历史超过 token budget 时，调用 LLM 将中间消息压缩为自然语言摘要。

### Cursor（游标）
Dream 系统中记录已处理历史位置的指针。存储在 `.dream_cursor` 文件中，实现增量处理。

## D

### Dispatch（分发）
Agent 间任务分发的机制。Agent A 通过 `dispatch_task` 工具写 JSON 文件到队列，Rust 核心轮询读取并转发给 Agent B。

### Dream
Agent 记忆整合过程。分析 `history.jsonl` 中的未处理条目，提取关键信息，合并到 `MEMORY.md`。通过受限工具循环（仅 `read_file` + `edit_file`）手术式编辑记忆。

## E

### Entry（入口）
Agent 或 Scene 的外部接入配置。定义了通过什么渠道（微信、飞书、Web API）与用户交互。

### Env Skill（环境技能）
场景级技能，该场景内所有 Agent 自动获得。与 Agent 个人技能不同，env skill 由场景配置定义。

## H

### Heartbeat（心跳）
Agent 的定期后台任务线程（默认 300s 周期）。执行：检查邮箱、读取聊天群组、执行定时任务、自动压缩。

### Hire（雇佣）
通过 `hire_agent` 工具请求创建新 Agent 的流程。需要管理员审批，通过后 Rust 核心自动创建配置文件并 spwan 新进程。

## J

### JSON-RPC
CocoCat 的层间通信协议。Rust 核心与 Python Agent 通过 stdin/stdout 传递 JSON-RPC 2.0 格式的单行消息。

## K

### KB（Knowledge Base，知识库）
结构化的知识存储。包含 `purpose.md`（用途描述）、`wiki/`（Wiki 页面）、`raw/sources/`（源文件）。通过两阶段 LLM 管线摄取。

## M

### MEMORY.md
Agent 的长期记忆文件。由 Dream 自动维护，包含关键决策、学到的事实、偏好和模式。注入到每个任务的 system prompt 中。

### MessageBus（消息总线）
聊天消息的持久化和路由系统。所有 agent 间通信记录在 `chat/group.jsonl`，提供统一的消息 ID 和游标追踪。

### MCP（Model Context Protocol）
模型上下文协议。CocoCat 通过 `mcp_call` 工具支持调用 MCP 服务器，扩展 Agent 能力。

## N

### Namespace（命名空间）
Linux 内核的隔离机制。CocoCat 支持通过 `unshare()` 创建隔离的命名空间，实现进程、文件系统、网络的完整隔离。

## P

### PermissionMode（权限模式）
工具权限级别：`READONLY < WORKSPACE_WRITE < FULL_ACCESS`。当前运行模式决定 Agent 可以调用的工具范围。

### Profile（个性配置）
Agent 的身份设定：角色、目标、性格特征、背景、规则。存储在 `profile.json`，首次创建后不可变。

## R

### ReAct（Reasoning + Acting）
Agent 的思考-行动循环：LLM 推理 → 决定调用工具 → 执行工具 → 观察结果 → 继续推理 → ... → 最终回复。

### Roster（花名册）
场景的成员列表。`scenes/{id}/roster.json` 定义哪些 Agent 属于该场景。

## S

### Sandbox（沙箱）
安全层集合，包括：CommandValidator、EnvironmentSanitizer、PathValidator、OutputTruncator。在工具执行前进行多层安全检查。

### Scene（场景）
工作上下文隔离单元。每个 Scene 有独立的 context、KB 挂载、roster、env skills。Agent 的 `scene` 字段决定其所属场景。

### Skill（技能）
Agent 可加载的独立能力单元。通过 `learn_skill` / `forget_skill` 管理。有 `public`（其他 agent 可见）和 `private`（仅自己可见）之分。

## T

### TOCTOU（Time of Check, Time of Use）
安全编程中常见的竞态条件问题：检查权限和使用资源之间存在时间窗口。CocoCat 通过原子写入和文件锁缓解此类问题。

### ToolRegistry
工具注册表。管理所有可用工具的注册、查找、权限检查和执行。通过 `create_default_registry()` 创建标准工具集。

## W

### Workspace（工作空间）
Agent 可以操作的文件目录范围。由 `COCOCAT_WORKSPACE` 环境变量定义，PathValidator 确保 Agent 不会访问此范围之外的文件。
