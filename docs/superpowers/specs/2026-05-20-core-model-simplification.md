# CocoCat 核心模型简化

**日期**：2026-05-20
**类型**：架构决策
**状态**：已确认

---

## 1. 当前问题

现有模型存在概念冗余：
- Coco（Main AI）和 kb-agent 被作为两个「固定 Agent」对待
- Agent 管理页列出的是 Agent 配置，却给人「团队成员在线」的错觉
- Scene-Agent 的绑定关系不清晰
- 前端设计容易陷入「多个 Agent 坐在工位上」的错误隐喻

## 2. 简化后的核心模型

### 2.1 三层架构

| 层级 | 组成 | 性质 |
|------|------|------|
| 持久层 | Coco | 唯一的调度核心，全局单例 |
| 组织层 | Scene | 工作上下文（KB 集 + context + worker 模板偏好） |
| 执行层 | Worker | Coco 按需 fork 的沙盒进程，执行完销毁 |

### 2.2 Coco

- Coco 是系统中**唯一的持久智能体**
- 它接收 session 上下文 → 推理 → 返回 / 调用工具 / fork worker
- 每次调用独立，按 session_id 隔离，天然支持并行
- 多渠道、多 Scene、多用户并发访问 Coco 不会混乱——它是无状态函数

### 2.3 Scene

- Scene = 一个工作上下文，包含：名称、描述、关联的 KB 列表、推荐的 worker 模板列表
- Scene 不绑定固定的 Agent，只绑定「这个场景下常用哪些 worker 模板」
- kb-agent 退化为一个内置 Scene：「知识库管理场景」，预置了 file 处理、索引相关的 worker 模板
- 用户创建 Scene = 定义一个新的工作上下文，不是分配固定的人

### 2.4 Worker

- Worker 是 Coco 通过 DAG 系统 fork 出来的**临时沙盒进程**
- 生命周期：创建 → 执行一个 task → 销毁
- Worker 使用的配置来自 Agent 模板（角色名、system prompt、tool 集）
- 多个 worker 可并行执行（DAG 的并行 Stage）
- 「多 Agent 协作」的本质 = Coco 同时分身出多个 worker 并行干活

### 2.5 Agent 模板

- 当前 Agents 页列出的 Agent 配置 → 重新定义为「Worker 模板」
- 模板定义了：角色名、system prompt、可用 tool 集、推荐模型
- 模板不「在线」也不「离线」——它只是一个配置，Coco 按需 fork
- 用户管理 Agent = 管理 Coco 可用的 worker 模板库

## 3. 对前端设计的影响

| 之前（错误） | 之后（正确） |
|-------------|-------------|
| Dashboard 展示 Agent 工位 | Dashboard 展示 Coco 状态 + 活跃 worker + DAG 进度 |
| Agents 页 = 团队成员列表 | Agents 页 = Worker 模板管理 |
| kb-agent 是固定 Agent | kb-agent 退化为内置 Scene |
| 「多 Agent」= 多个人格 | 「多 Agent」= Coco 的并行分身 |

## 4. 并发模型

- Coco 调用是异步无状态的，按 session_id 隔离
- 不同 Scene / 渠道 / 用户天然并行
- 瓶颈仅在 LLM API 并发额度和系统沙盒资源
- 无需额外的事务或锁机制

## 5. 迁移路径

1. kb-agent 从「固定 Agent」改为「内置 Scene」，其工具和 prompt 配置移至 Scene 配置中
2. Agent 管理页 UI 文案从「Agent」改为「Worker 模板」
3. Dashboard 移除工位概念，聚焦 Coco + 活跃 DAG 任务 + worker 快照
4. 数据库层面：不需要 Schema 变更，仅前端概念层调整
