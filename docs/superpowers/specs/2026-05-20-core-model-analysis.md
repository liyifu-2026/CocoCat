# CocoCat 核心模型 · 现状分析

**日期**：2026-05-20
**类型**：代码分析
**状态**：已完成

---

## 1. 执行模型：真相

### 1.1 Chat 请求如何执行

用户发消息 → `POST /api/chat` → **不走 AgentPool**。而是：

```
sandbox_provider.run_once(prompt, agent_id="main", tools=main_ai())
  → LocalExecutor.create()   → Sandbox(id="local-N", ...)  ← 仅命名，无进程隔离
  → LocalExecutor.run()      → _make_and_run_agent()
      → Agent(id="main", role=WORKER, tools=...)  ← 临时 Python 对象
      → agent.run(prompt)    → ReAct 循环
  → LocalExecutor.destroy()  → 从 dict 移除
```

**结论：Chat 中的 Coco 是每次请求临时创建的 `Agent` 对象，用完即弃。** 不是持久的「Coco 坐在调度台」。

### 1.2 kb-agent 如何执行

`POST /api/kb-chat` → 同样模式，`agent_id="kb-agent"`，工具集使用 `resident(kb_agent=True)`（多了文件读写和 KB 管理工具）。

### 1.3 AgentPool 的实际角色

- 启动时加载 Coco 和 kb-agent 为 RESIDENT，存入 `_agents` dict
- **仅用于两件事**：
  1. Cron 定时任务（从池中取出 resident agent 执行）
  2. DAG 分发时的 fallback（没有 SandboxProvider 时才用池中 WORKER）
- Chat 请求**完全绕过** AgentPool

### 1.4 Worker = 临时对象，不是独立进程

- `LocalExecutor` 中的「Sandbox」只是命名——本质是 `Sandbox(id, permissions)` 空对象
- Agent 创建/销毁 = Python 对象生命周期
- 无进程隔离（除非启用 CubeSandbox MicroVM 模式，需 `--cube-sandbox` 参数）

### 1.5 DAG 分发

```
Coco 调用 dispatch_task(run_id, task_id, prompt)
  → 任务写入 DagStore，状态 = pending
  → TaskWorker 每 10s 轮询
      → 取 pending 任务
      → sandbox_provider.run_once(agent_id=f"sub-{task_id}", tools=worker())
          → 临时 Agent(WORKER)，完整工具集（bash/browser/file/web）
      → 状态更新为 done/failed
  → 全部任务完成后：再创建一个临时 Agent 让 Coco 总结结果
```

---

## 2. 持久层：真正存在的东西

### 2.1 固定角色

| 角色 | 配置位置 | 性质 |
|------|---------|------|
| Coco | `config/residents/coco.yaml`（id: "main"） | RESIDENT，启动加载，cron 用 |
| kb-agent | `config/residents/kb-agent.yaml` | RESIDENT，启动加载，3 个 cron 任务 |

两者都是 YAML 配置 + 启动时加载到 AgentPool。Chat 时不走池，各自独立创建临时 Agent。

### 2.2 Agent 配置

- `agents/` 目录下有 agent profile 文件（profile.yaml, memory.md, pinned.md）
- `agents` 数据库表存储 Agent 元数据（名称、模型、状态、scene_id）
- 「Agent 管理页」管理的是这些**配置记录**，不是运行中的实例

### 2.3 Scene 与 Agent 的关系

- Scene 在 DB 中有 `agent_id` 列（可选，一对一）
- 通过向导创建 Scene 时，**同时创建一个 Agent** 并绑定
- Scene YAML 中有 `roster` 字段，但**代码中未使用**，纯占位
- Scene 运行时（SceneKeeper）创建 `scene-{scene_id}` 临时 Agent

### 2.4 会话持久化

- Chat 的 session 以 JSONL 文件存储在 `agents/{agent_id}/sessions/` 目录
- Coco 的会话存在 `agents/main/sessions/`，kb-agent 的存在 `agents/kb-agent/sessions/`

---

## 3. 并发模型

- FastAPI 异步，多请求并行
- 每个 Chat 请求独立创建临时 Agent，互不干扰
- `LocalExecutor` 有 `semaphore(max_workers=4)` 限制并发数
- 不同 session_id 天然隔离

---

## 4. 现有模型的问题（保持客观）

1. **AgentPool 和 Sandbox 双轨**：AgentPool 加载 resident agent 但 Chat 不用它，造成认知混乱
2. **roster 字段名存实亡**：YAML 中定义了 roster，代码不读取
3. **kb-agent 是否必须作为独立 Agent**：它和 Coco 的唯一区别是工具集不同。现有架构下它作为独立 RESIDENT 存在
4. **Scene 创建时自动绑定 Agent**：这导致 Scene 总是 1:1 绑定一个 Agent，限制了 Scene 作为「纯上下文」的可能性
5. **"Sandbox" 命名有误导性**：默认模式下无任何沙盒隔离

---

## 5. 已确认的重构决策（第一轮）

| # | 决策 | 说明 |
|---|------|------|
| 1 | **砍 AgentPool，统一走 Executor** | 所有 Agent 执行按需临时创建，无双轨 |
| 2 | **删 roster 字段** | Scene YAML 和 SceneStore 移除 roster |
| 3 | **砍 Scene 自动绑定 Agent** | `create_scene_full()` 不再同时创建 Agent |
| 4 | **kb-agent 退化** | 不再作为独立 RESIDENT。知识库管理作为内置 Scene，Coco 通过 sub_agent 处理 |
| 5 | **重命名 Sandbox 类** | `LocalExecutor` → `InProcessExecutor`，`SandboxProvider` → `ExecutorProvider` |
| 6 | ~~PathSandbox~~ | 暂不启用 |

## 6. 第二轮决策

| # | 决策 | 说明 |
|---|------|------|
| 7 | **Session 按 Scene×User 存** | `scenes/{scene_id}/sessions/{user_id}/` |
| 8 | **Memory 按 Scene×User 存** | `scenes/{scene_id}/memory/{user_id}/`，含 facts/dreams/summaries/compilations |
| 9 | **Cron 定义双重来源** | 系统级：`config/cron.yaml`。用户级：DB cron 表 |
| 10 | **Cron 执行统一路径** | CronWorker → `ExecutorProvider.run_once(scene_id, user_id)` → 临时 Agent |
| 11 | **删 agents 数据库表** | 原表 `agents` 改名 `worker_templates` → 后又确认删：Worker 就是 sub_agent 工具，无需模板管理页 |
| 12 | **删 Scene.agent_id 列** | Scene 不再绑定 Agent |
| 13 | **渠道系统简化** | SceneKeeper 剔除 agent 查找：渠道消息 → Scene → `ExecutorProvider.run_once()` |
| 14 | **砍 DAG 系统** | 全部移除：DagStore、TaskWorker._process_dag、DAG 工具（define_dag/append_stage/dispatch_task 等）。sub_agent 同步执行 |
| 15 | **砍 Workspace 持久目录** | sub_agent 临时目录，执行完清空 |
| 16 | **引入用户级隔离** | Scene 共享，但 scene×user 的 session 和 memory 独立 |
| 17 | **新增「我的 Coco」配置** | 每用户可自定义：模型、system prompt 覆盖、渠道认证 |

## 7. 重构后的终极模型

```
CocoCat = 三样东西：

1. Coco（一只猫）
   用户对话 → ExecutorProvider.run_once(user_coco_config)
   → 临时 Agent，按需创建，用完销毁
   工具集：sub_agent + memory + kb + web + file_rw + browser + meta

2. sub_agent（Coco 的分身工具）
   Coco 调用 sub_agent(prompt, tools) → fork 临时 worker → 执行 → 返回 → 销毁
   并行只需多次调用。无 DAG、无模板、无状态。

3. Scene（工作上下文）
   name + context + kbs + skills + channels
   团队共享。session 和 memory 按 scene×user 隔离。
```

### 执行路径

```
用户发消息（Chat / 渠道）
  → 找到当前 Scene
  → 加载用户「我的 Coco」配置（模型、prompt覆盖）
  → ExecutorProvider.run_once(scene_id, user_id, tools)
    → InProcessExecutor（默认）或 CubeSandboxExecutor
      → 临时 Agent，加载 Scene context + KB + skills + 用户偏好
      → agent.run(prompt) → ReAct（可调用 sub_agent 分身）
    → destroy()
  → 结果返回，session 写入 scenes/{scene}/sessions/{user}/
```

### 被砍掉的东西

- AgentPool / RESIDENT agent 概念
- kb-agent 独立角色
- Agent/Worker 模板管理页
- DAG 系统（stages、task queue、DagStore）
- roster 字段
- Scene-agent 绑定
- Workspace 持久目录

## 8. 第三轮决策（实现细节）

| # | 决策 | 说明 |
|---|------|------|
| 18 | **Mode 定义存 YAML** | `config/modes/{mode_id}.yaml`，每 Mode 包含 system_prompt + tools + skills |
| 19 | **首批两个 Mode** | default（主人格）+ kb-admin（知识库管理） |
| 20 | **Mode 切换双通道** | 系统自动（prompt 指令）+ 手动（前端选择器 / `/mode` 命令） |
| 21 | **System prompt 并入 Mode YAML** | 废弃 `config/prompts/` 和 Python 常量，`agent_builder/prompt.py` 清理 |
| 22 | **ToolCatalog 退化为注册表** | 无 preset，Mode YAML 列工具名。工具可重叠。 |
| 23 | **Skills 两层叠加** | Mode 自带 skills + Scene 可选附加 skills，运行时合并 |
| 24 | **KB 摄入由 Coco 处理** | 用户上传文件 → Coco 在 kb-admin Mode 下调用工具处理。IngestPipeline 保留作为工具实现 |
| 25 | **渠道认证归 Scene** | 无 `user_channels` 表。外部客户通过 Scene 渠道（WeChat bot 等）接入 |
| 26 | **删 `config/residents/` + `config/prompts/`** | 功能迁入 `config/modes/` 和 `config/cron.yaml` |
| 27 | **Memory 编译 cron 不变** | 每 Scene 独立跑，系统级 cron，主人格执行 |
| 28 | **Session 不清理、续接、无上限** | 渠道天然无新开会话概念 |
| 29 | **数据库删 3 表** | agents、dag_runs、tasks。scenes 删 agent_id。无新增表 |
| 30 | **Mode 切换 API 统一** | `POST /api/chat { content, scene_id, mode }`，默认主人格 |
| 31 | **Route 改造** | 删 agents.py + dag.py。改 chat/scenes/knowledge/ws/cron。其余保留 |

## 9. 对前端的影响（最终版）

砍掉的：
- ~~Agents 管理页~~ — 无模板管理
- ~~DAG 可视化（L3/L4）~~ — 无 DAG 系统
- ~~Studio~~ — 无模板编排
- ~~SceneRun~~ — 并入 Chat
- ~~ChatHistory 独立页~~ — 降为 Chat 面板
- ~~「我的 Coco」~~ — 被 Mode 系统替代，仅保留主题/语言/密码

保留重做：
- Login + Welcome + Onboarding — 冷启动链
- Dashboard — Coco 状态 + 活跃 sub_agent + 近期活动 + Scene 信息
- Chat — 加 Mode 选择器 + sub_agent 调用展示
- Scenes + SceneNew — 管理场景
- Knowledge + KnowledgeDetail — KB 管理
- MemoryBrowser — 记忆浏览
- NotificationCenter — 通知面板
- GlobalSearch — ⌘K 搜索
- SystemStatus — 系统健康

新增：
- Mode 选择器（Chat 内组件，非独立页面）
