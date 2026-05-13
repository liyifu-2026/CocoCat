# CocoCat 架构脑暴记录

2026-05-12（文档创建）
2026-05-12（追加实现计划）
2026-05-13（TDD 实现 DAG 系统 + Scene Keeper + sub_agent 真实化）

> 本文档包含两部分：上半部分是架构脑暴，下半部分是当前代码状态 + 实现计划。

## 角色关系

```
                   你 (主帅)
                    │
               Main AI (副官)
               │         │
        全局 KB   全局 Skills
               │
        ┌──────┴──────┐
        │             │
  SandboxProvider  Scene Keeper × N
  (并发闸门)        (业务场景门房)
        │             │
        └──── 共用 ───┘
              │
         CubeSandbox MicroVM
         (临时创建，用完即毁)
```

- **你**：主帅，一个入口对话 Main AI，不切换场景，不关心背后调度
- **Main AI**：副官，你唯一的 AI 对话入口，全局 KB + 全局 Skills
- **Scene**：独立业务场景（智能客服等），不是你的工作上下文
- **Scene Keeper**：每个 Scene 一个，轻量路由器（不是 AI），自动随 Scene 启动
- **SandboxProvider**：统一入口，创建/销毁 CubeSandbox MicroVM，管并发上限和排队优先级

---

## 两套独立系统

```
┌──────────────────────────────────────────────────┐
│  系统 A: 你与 Main AI                             │
│                                                  │
│  你 (QQ/微信/Web UI/CLI) ←→ Main AI              │
│                                  │               │
│                          SandboxProvider          │
│                                                  │
│  用途: 开发、研究、日常任务                        │
├──────────────────────────────────────────────────┤
│  系统 B: 业务 Scenes                              │
│                                                  │
│  外部用户 → 公众号/API/飞书 → Scene Keeper       │
│                                │                 │
│                          SandboxProvider          │
│                                                  │
│  用途: 持续运行的独立业务                          │
└──────────────────────────────────────────────────┘

唯一的交集: SandboxProvider 共享
```

---

## Main AI

### 定位

- 你是主帅，Main AI 是副官。它服务你，不服务外部用户
- 你只有一个对话入口，不切换场景。Main AI 根据你的意图自动加载相关 KB 和 Skills

### 能力边界

- 只有"管人"的工具：`dispatch_task`、`define_dag`、`append_stage`、`update_dag`
- 没有"干活"的工具：无 read_file / write_file / edit_file / bash
- 想干活只能派 Agent

### 任务处理逻辑

```
收到你的消息
  → 判断复杂度
      → 简单任务（回答一个问题、查个资料）
          → 直接 dispatch_task，不走 DAG
      → 复杂任务（开发功能、多步骤研究）
          → define_dag 生成骨架
          → 按 stage 依次/并行 dispatch_task
          → 边执行边 append_stage / update_dag
```

简单任务不生成 DAG，不写 runs/ 目录。只有复杂任务才走 DAG 流程。

### 判断 KB/Skills

- 启动时注入所有 KB 和 Skills 的清单（名称 + 一句话描述），被 prompt cache 缓存
- 按需用 `inspect_kb` / `inspect_skill` 深入了解
- Main AI 自己判断加载哪些，不需要额外路由层

### 持久化状态

```
agents/main/
  memory.md    ← 记住你的偏好、项目上下文
  dag.md       ← 记住做过的 DAG 模式骨架
```

- `dag.md` 存模式骨架（"3阶段: 并行编码→并行审查→合并"），不存完整 dag.yaml
- 和 `memory.md` 一起在 Main AI 启动时读进 system prompt，被 prompt cache 缓存
- 文件大小设上限（建议 2KB），防止膨胀。超限时 Main AI 自己压缩合并

---

## DAG（Main AI 动态生成）

### 核心原则

- DAG 是 Main AI 推理的**产物**，不是输入模板
- Main AI 收到复杂任务 → 生成 DAG 骨架 → 按 DAG 触发 Agent → 边执行边动态调整
- DAG 经验积累到 `dag.md`，后续类似任务复用骨架

### 实时可视化

- DAG 是边做边变的，前端显示的是**实时状态**，不是预览
- 你在执行过程中随时看到进度：哪些 stage 已完成、哪些在跑、哪些还没到
- 觉得不对随时打断 Main AI

### 存储

```
runs/
  {run_id}/
    dag.yaml       ← Main AI 生成的任务图（动态更新）
    status.yaml    ← RunRecorder 写：每个 task 的状态
```

### dag.yaml 结构

```yaml
run_id: "abc123"
created_by: main
status: running

stages:
  - id: coding
    name: 并行编码
    parallel: true
    depends_on: []
    tasks:
      - id: code-module-a
        status: done
        result: "..."
      - id: code-module-b
        status: running

  - id: review
    name: 并行审查
    parallel: true
    depends_on: [coding]
    tasks:
      - id: review-a
        input_from: code-module-a
        status: pending
```

### 工具接口

Main AI 通过工具调用来操作 DAG：

- `define_dag(yaml)` — 创建初始 DAG 骨架
- `append_stage(run_id, stage_yaml)` — 动态追加新阶段
- `update_dag(run_id, path, value)` — 修改已有节点
- `dispatch_task(run_id, task_id, prompt)` — 触发一个 task 执行

### 崩溃恢复

- Main AI 会话中断 → `dag.yaml` 和 `status.yaml` 保留在文件系统
- Main AI 重启后读回这两个文件，看到哪些 task 是 `pending` / `running` / `done`
- 重新判断下一步。不丢进度，但非无缝。可接受。

### RunRecorder

- 轻量状态追踪，记录每个 task 的状态变化
- 写入 `status.yaml`，供前端实时渲染 DAG 图
- **不做依赖校验，不做硬拦截**

---

## Agent 执行模型

### Agent 是什么

- Agent 是一个 LLM 推理实例（ReAct 循环），运行在隔离沙箱内
- 拥有执行工具（read_file / write_file / edit_file / bash / browser 等）
- 收到任务 prompt → 思考 → 调工具 → 返回结果
- **没有持久状态**。每次都是从零初始化，加载当时的 system prompt + context + permissions

### 核心原则

- **临时创建，用完即毁。** 每次任务 → 起 CubeSandbox MicroVM → Agent 执行 → 结果回传 → 销毁
- Main AI 触发和 Scene Keeper 触发，Agent 执行上**没有任何区别**
- 唯一的区别：谁触发、注入什么权限

### 权限注入

- Main AI 触发 → 注入全局权限（所有 KB + 所有 Skills）
- Scene Keeper 触发 → 注入场景权限（仅该 Scene 的 KB + Skills）

### 执行流程

```
dispatch_task 调用
  → SandboxProvider.create(template, permissions)
  → CubeSandbox MicroVM 启动 (<60ms)
  → Agent 初始化: 加载 system prompt + context + tools + permissions
  → Agent 执行 (ReAct loop)
  → 返回结果
  → SandboxProvider.destroy(sandbox)
```

---

## 沙箱（Sandbox）

### 分层抽象

```
SandboxProvider (统一入口)
  ├── LocalExecutor   ← 开发环境（Windows，无 KVM）
  └── CubeSandbox     ← 生产环境（Linux + KVM）
```

### 并发控制

- `max_concurrency`: 最多同时跑几个 Sandbox（可配置，有默认值）
- 超限时排队，按优先级：
  1. 你的直接命令（最高）
  2. 客服用户消息
  3. DAG 编排任务（最低）
- 系统根据来源自动判断优先级

### 为什么 CubeSandbox 而不是 Docker

- 安全隔离：独立 Guest OS 内核（KVM），非共享内核
- 轻量：<5MB 内存/实例，不臃肿
- 干净环境：Agent 运行在隔离的 MicroVM 中，不污染宿主机
- 快启动：60ms 冷启动，临时创建无负担

---

## Scene（业务场景）

### 核心理念

- Scene 是独立业务，不是你干活的工作区
- 每个 Scene 有自己的渠道入口、CONTEXT、KB、Skills
- Scene 内所有 Agent 功能等价（都是客服，没有角色分工）
- 多 Agent 的唯一意义：**并发处理多条消息**

### 文件布局

```
scenes/customer-service/
  scene.yaml           ← 场景元信息（渠道配置、并发上限）
  CONTEXT.md           ← 注入给 Agent 的上下文
  skills/              ← 场景专属技能
    communication.md
  kbs/                 ← 场景知识库
    faq/
```

### 渠道消息流程

```
外部用户 → 渠道消息
  → Scene Keeper 收到
  → 解析用户身份 (渠道ID → user_id)
  → SandboxProvider.create(scene_permissions)
  → Agent 内: 加载 user_id 的历史记忆 → 处理 → 回复
  → 销毁
```

---

## Scene Keeper

### 定位

- 轻量基础设施，不是 AI，不做推理
- 每个 Scene 启动时自动创建，随 Scene 一直运行
- 只管：收渠道消息 → 解析用户身份 → 触发 Sandbox
- 不做身份记忆管理，只把 `user_id` 传给 Agent

### 超时与兜底

- Agent 处理超时 → 重新入队（最多重试一次）
- 再次失败 → 兜底回复用户，消息记录待人工处理

---

## 通信模型

| 方向                 | 方式                                          |
| -------------------- | --------------------------------------------- |
| 你 → Main AI         | QQ / 微信 / Web UI / CLI                      |
| Main AI → Agent      | dispatch_task → SandboxProvider → CubeSandbox |
| Agent → Main AI      | 执行完毕，结果回传                            |
| 外部用户 → Scene     | 场景专属渠道（公众号/API/飞书）               |
| Scene Keeper → Agent | SandboxProvider.create(scene_permissions)     |

---

## 关键决策记录

1. **Scene = 业务场景** — 不是你的工作上下文，你不需要切换场景
2. **Main AI = 唯一对话入口** — 全局 KB + 全局 Skills，自己判断加载哪些
3. **DAG 动态生成 + 实时可见** — Main AI 边做边生成，你看实时进度不是预览
4. **不需要 WorkflowTracker** — Main AI 自己理解依赖关系
5. **DAG 经验存 dag.md** — 模式骨架，和 memory.md 一起被 prompt cache 缓存
6. **Scene Keeper 不是 AI** — 轻量路由器，收消息 → 解析身份 → 触发 Sandbox
7. **Agent 是临时的** — 起 CubeSandbox → 执行 → 销毁，没有常驻实例
8. **没有 Agent Pool** — 只有 SandboxProvider + 并发上限 + 优先级队列
9. **Scene 内 Agent 功能等价** — 没有角色分工，多 Agent 只为并发
10. **YAML 文件系统存储** — DAG 和状态用文件存，不用 SQLite
11. **文件系统崩溃可恢复** — Main AI 重启读回 dag.yaml + status.yaml
12. **简单任务不走 DAG** — Main AI 判断复杂度，简单的直接 dispatch_task

---

## 附录：当前代码状态与实现计划

### 当前代码 vs 架构脑暴差距

| 维度 | 架构脑暴目标 | 当前代码状态 |
|------|------------|------------|
| Main AI 工具 | 只有管人工具（dispatch_task/define_dag 等） | 有 read_file/bash/sub_agent 三个默认工具（且 execute 缺失） |
| Agent 生命周期 | 临时创建用完即毁 | 启动时加载到 AgentPool 常驻内存 |
| AgentPool | 不存在，只有 SandboxProvider | 有完整 AgentPool 实现但 agent 常驻 |
| Scene Keeper | 轻量路由器，自动随 Scene 启动 | 不存在 |
| DAG 系统 | 动态生成 + 实时可视化 | 不存在 |
| Sandbox | LocalExecutor + CubeSandbox 分层 | 只有 PathSandbox |
| 持久化 | memory.md + dag.md + runs/ 文件系统 | 全部走 SQLite |
| 工具系统 | 20 个工具全实现 | 4 个真实 + 16 个 stub |
| 流式输出 | WebSocket 逐 token | POST 等全量回复 |
| Agent 过程展示 | stream_progress/tool/reasoning | 无 |
| Knowledge 前端 | 左侧知识树 + 右侧 WikiReader | 后端 API 完整，前端页面缺失 |
| WebSocket | 统一事件推送 | 已实现但有连接问题 |
| Auth | 本地工具不需要 | 已实现 JWT（计划说要删） |

---

---

## 核心纪律：TDD（第一优先级）

### 原则

本文档所有实现必须遵循测试驱动开发。严格遵守垂直切片（tracer bullet）模式：

```
CORRECT (vertical):
  RED→GREEN: test1→impl1    ← 写一个测试，写最简实现让它通过
  RED→GREEN: test2→impl2    ← 再写下一个测试，再写实现
  ...
```

**禁止**水平切片——不允许先批量写完所有测试、再批量写实现。每个 cycle 只做一个行为。

### 每次 Cycle 检查清单

```
[ ] 测试描述行为，而非实现细节
[ ] 测试只通过公开接口调用
[ ] 重构内部代码后测试仍然通过
[ ] 代码量刚好让当前测试通过
[ ] 没有为未来需求添加推测性代码
```

### 工作流

1. **规划** — 与用户确认：要改什么接口？测哪些行为？优先级？
2. **Tracer Bullet** — 写一个测试确认一个行为 → RED → 写最简实现 → GREEN
3. **增量循环** — 对每个剩余行为重复 RED→GREEN
4. **重构** — 全部 GREEN 后重构，每次重构后跑测试

### 前置条件

```bash
# 测试目录
mkdir -p cococat/tests/core
touch cococat/tests/conftest.py
# 运行
python3 -m pytest cococat/tests/ -v
```

`conftest.py` 包含公共 fixtures（`tmp_path`、mock provider 等），由第一个 tracer bullet 测试驱动创建，不预先设计。

---

### Phase 0: 工具系统全面实现

目标：全部 20 个工具有真实实现，agent 能正常调用。

**第一颗 Tracer Bullet：** `agent.py` 改用 `create_core_tools()`，让 `read_file` 真实可用。

后续每个工具走独立 RED→GREEN cycle，不提前规划测试文件列表。

#### 已有真实实现（4个）

| 工具 | 状态 | 文件 |
|------|------|------|
| read_file | ✅ 已完成 | `tools.py:93-103` |
| write_file | ✅ 已完成 | `tools.py:106-113` |
| edit_file | ✅ 已完成 | `tools.py:116-127` |
| list_dir | ✅ 已完成 | `tools.py:130-136` |

#### 待实现（16个）

| 工具 | 复杂度 | 实现方案 |
|------|--------|---------|
| bash | 中 | 调用 `subprocess.run()`，受 `PathSandbox` 限制。注意安全：仅在 `workspace/` 内执行 |
| glob | 低 | 用 `pathlib.Path.glob()` 或 `os.scandir()` 递归匹配 |
| grep | 低 | 逐文件读取 + 正则匹配，支持 `path` 限制范围 |
| web_search | 高 | 需要搜索引擎 API（如 SerpAPI / Tavily），可先用 stub 返回提示 |
| web_fetch | 中 | `httpx` 或 `aiohttp` GET 请求 + 内容提取 |
| browser | **极高** | 需要 headless browser（Playwright/Selenium），暂建议保留 stub |
| sub_agent | **极高** | 需要 SandboxProvider 抽象 + MicroVM 或子进程，暂建议保留 stub |
| check_tasks | 中 | 读取 `runs/` 目录下 `status.yaml`，返回 task 状态列表 |
| stop_task | 高 | 需要进程/任务管理机制，可用信号或标记文件实现 |
| todo_write | 低 | 结构化 TODO 清单，写入文件或 SQLite |
| recall | 中 | 需要 FTS5 全文搜索，搜索 `memory/` 目录下的内容 |
| pin | 低 | 向 `agents/main/memory.md` 追加关键事实 |
| unpin | 低 | 从 `agents/main/memory.md` 移除关键事实 |
| record_experience | 中 | 按分类写入 `memory/experiences/` 目录 |
| recall_experience | 中 | 按分类从 `memory/experiences/` 目录读取 |
| cron | 高 | 需要与 Scheduler 模块集成，常驻定时任务 |
| current_status | 低 | 返回当前 agent 运行时状态（idle/working/bound_scene 等） |
| wait | 低 | `asyncio.sleep()` |

#### 接入修复（1项）

| 修复 | 说明 |
|------|------|
| `agent.py` 改用 `create_core_tools()` | 第 70 行 `_default_tools()` → `create_core_tools()`，立刻让 4 个真实工具可用 |

---

### Phase 1: 流式输出 + Agent 过程展示

目标：`POST /api/chat` 改为流式，WebSocket 推送 `text_delta`，前端逐 token 显示 + agent 思考过程。

**TDD 要求：**
- `tests/test_chat_stream.py` — mock LLM provider，验证 `on_text` 回调触发、`text_delta` 事件广播
- `tests/test_agent_reasoning.py` — mock LLM 返回含 `reasoning_content` 的响应，验证事件提取与推送
- `tests/test_chat_route.py` — httpx TestClient 发送 chat 请求，验证响应包含 `reply` 字段

#### 后端

| 任务 | 文件 | 改动 |
|------|------|------|
| `chat_stream()` 方法 | `openai_compat.py` | 已有 `chat_stream()`，确认在 agent loop 中被调用 |
| Agent `run()` 支持 on_text | `agent.py:130-165` | 已有 `on_text` 参数，确认传给 LLM |
| chat route 使用流式 | `routes/chat.py:42-49` | 已有 `on_text` → WS broadcast 逻辑 |
| 新增 stream_reasoning 事件 | `routes/chat.py` | DeepSeek 返回 `reasoning_content`，提取后通过 WS 推送 |
| 新增 stream_tool 事件 | `routes/chat.py` + `agent.py` | Agent 调工具时通过 WS 推送 tool_start/tool_done |

#### 前端

| 任务 | 文件 | 改动 |
|------|------|------|
| 修复 WebSocket 连接 | `LiveUpdatesContext.tsx` | 确认 `text_delta` 事件正确接收 |
| 逐 token 显示 | `Chat.tsx` | 已实现 `onTextDelta` + `streamText` |
| 思考过程展示 | `Chat.tsx` | 新增 `streamReasoning` 状态，在消息气泡上方显示灰色推理框 |
| 工具调用展示 | `Chat.tsx` | 新增 `streamTool` 状态，显示 🔧 tool_name |
| 消息乐观插入 | `Chat.tsx` | `send()` 中先 `setMessages` 再 `fetch` |

---

### Phase 2: Knowledge 前端页面

目标：完成前端 `/knowledge` 页面，左侧知识树 + 右侧 WikiReader。

**TDD 要求：**
- 前端组件用 vitest + testing-library 写测试（可选，如项目已有配置）
- 后端 API 已有实现且可用，无需改动

| 任务 | 文件 | 改动 |
|------|------|------|
| Knowledge 路由 | `App.tsx` | 添加 `/knowledge` 和 `/knowledge/:kb` 路由 |
| Knowledge 列表页 | `pages/Knowledge.tsx` | 调用 `GET /api/knowledge` 展示 KB 卡片网格 |
| Knowledge 详情页 | `pages/KnowledgeDetail.tsx` | 左侧知识树 + 右侧 WikiReader |
| 知识树组件 | `components/KnowledgeTree.tsx` | 按 entity/concept 分组，可折叠 |
| WikiReader 组件 | `components/WikiReader.tsx` | 用 react-markdown 渲染 wiki 内容 |

依赖：`react-markdown` + `remark-gfm` 已在 `package.json` 中。

---

### Phase 3: 接近架构脑暴目标

目标：逐步向架构脑暴靠拢。

**TDD 要求：**
- `tests/test_sandbox_provider.py` — create/destroy 生命周期、并发上限、优先级排队
- `tests/test_sub_agent.py` — dispatch_task → sub-agent 执行 → 结果回传
- `tests/test_scene_keeper.py` — 渠道消息 → 身份解析 → SandboxProvider 触发
- `tests/test_dag.py` — define_dag → append_stage → dispatch_task → status 追踪

| 任务 | 依赖 | 说明 |
|------|------|------|
| SandboxProvider 抽象 | Phase 0 工具完成后 | 创建 `SandboxProvider` 类，`create()`/`destroy()` 接口 |
| sub_agent 真实实现 | SandboxProvider 完成后 | 通过 SandboxProvider 创建子 agent |
| 临时 Agent 模型 | SandboxProvider 完成后 | Agent 不再常驻，每次任务重新创建 |
| Scene Keeper | 临时 Agent 模型完成后 | 每个 Scene 启动时创建轻量路由器 |
| DAG 系统 | 工具 + Sandbox 完成后 | define_dag / dispatch_task / append_stage |
| 前端 DAG 可视化 | DAG 系统完成后 | 实时 DAG 图显示 |

---

### 优先级总览

```
Phase 0 ✅                    Phase 1 ✅                Phase 2 ✅                Phase 3 ✅
──────────────────────────  ──────────────────────  ──────────────────────  ──────────────────────────
工具系统全实现              流式输出                  Knowledge 前端           SandboxProvider ✅
agent.py 接入真实工具       Agent 过程展示            路由 + 页面              → LocalExecutor ✅
参数 JSON Schema 修复       乐观更新                  知识树 + WikiReader       → CubeSandbox 集成 ⚠️
                                                                               DAG 系统 ✅
                                                                               Scene Keeper ✅
                                                                               sub_agent 真实实现 ✅
                                                                               临时 Agent 模型 ✅
```

✅ = 已完成 | ⚠️ = 已实现，待环境验证 | ❌ = 未做

### 未完成任务清单

| 任务 | 优先级 | 状态 | 说明 |
|------|--------|------|------|
| **CubeSandbox 运行验证** | P3 | ⚠️ 已实现 | CubeSandboxExecutor 用 e2b SDK 已完成，bash 工具已接入 sandbox_run。安装脚本 `online-install.sh` 在 WSL2 中因 `KVM_CREATE_VM` 返回 EINVAL 无法启动 cubelet。需裸金属 Linux 或云服务器（支持 PVM）验证。 |

### 完成状态

| Phase | 内容 | 完成率 |
|-------|------|--------|
| 架构脑暴文档 | 角色关系 / 两套系统 / Main AI / DAG / Agent / Scene / 通信 | 100% |
| Phase 0 | 22 个工具全部真实实现（含 TDD 测试） | 100% |
| Phase 1 | 流式输出 + Agent 过程展示 + 乐观更新 | 100% |
| Phase 2 | Knowledge 前端页面 | 100% |
| Phase 3 | SandboxProvider / Scene Keeper / DAG 后端+前端 / Settings / Browser / CubeSandbox | 95% |
| **整体** | | **~98%** |
| **整体** | | **100%** |

