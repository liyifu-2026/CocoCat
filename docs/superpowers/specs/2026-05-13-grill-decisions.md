# 架构讨论决策记录

2026-05-13

> 本文档是 2026-05-12 架构脑暴文档的 grill 讨论产物。记录所有讨论中落地的决策、发现并修复的代码与文档矛盾、以及后续执行计划。

---

## 决策一览

### 1. Main AI 能力边界

**原文档说**：Main AI 只有管人工具，没有读文件/写文件/bash。

**讨论结论**：保留必要工具。Main AI 需要读 memory.md、dag.md、KB/Skills 才能有效工作。拆离是 Phase 3 的事，等 chat route 从 AgentPool 切换到 SandboxProvider 之后再做。

### 2. 跨 Agent 共享状态

**问题**：临时 Agent 用完即毁，DAG 场景需要共享 workspace，Scene 多轮对话需要共享对话历史。

**决策**：SandboxProvider 创建沙箱时挂载共享目录。

| 场景 | 共享方式 |
|------|---------|
| DAG 工程 | SandboxProvider 挂载同一 workspace 目录 |
| Scene 对话 | Agent 注入 user_id，从 `sessions/{user_id}/` 读历史文件 |
| 并行同一 stage | 不同 task 写不同文件路径 |

### 3. 用户可感知延迟上限

**决策**：5 秒。从 dispatch_task 调用到第一条 token 出现。

### 4. Scene Keeper 触发颗粒度

**问题**：每条消息（包括「谢谢」「？」）都起 Agent 是否浪费？

**决策**：坚持用完即毁。每条消息起一个 Agent。不接受会话级复用。理由：与 DAG 崩溃恢复逻辑一致（都是读文件恢复上下文），无生命周期管理负担，60ms MicroVM 冷启动远在 5 秒预算内。

### 5. status.yaml / RunRecorder 去留

**问题**：文档设计了 status.yaml 存任务状态，dag.yaml 存结构。但代码中 dag.yaml 一身兼两职（结构 + 状态），status.yaml 和 RunRecorder 从未存在。

**决策**：删除文档中的 status.yaml 和 RunRecorder 概念。承认 dag.yaml 单文件同时承载结构和状态。

### 6. 简单任务 vs 复杂任务判定

**问题**：文档说 Main AI 判断复杂度，简单的直接 dispatch_task，复杂的走 DAG。但 dispatch_task 代码强依赖 DAG——必须传 run_id。

**决策**：一切任务皆 DAG。简单任务是最小的 DAG（1 stage  1 task）。删除文档中「简单任务不走 DAG」的说法。

### 7. AgentPool 去留

**问题**：文档说「没有 AgentPool」，代码有完整 AgentPool 且被 chat route、bridge、worker 深度使用。

**第一次决策**（讨论中）：保留 AgentPool，改文档。

**最终决策**（用户推翻）：要做临时 Agent 模型，去掉 AgentPool。但需 CubeSandbox 部署完后才切——当前保留 AgentPool 作为过渡。

### 8. JWT / Auth 删除

**决策**：已删除。`cococat/routes/auth.py` 整个文件删除，`cococat/routes/ws.py` 中 JWT Token 校验代码移除。

### 9. browser 工具补全

**决策**：从原来 3 个操作（navigate、get_text、screenshot）扩展到 9 个。新增 click、type、get_content、scroll、execute_js、go_back。所有 action 支持可选的 `url` 参数，在单次调用内完成导航 + 操作。

### 10. 工具权限分离时机

**决策**：Phase 3 再做。当前 Main AI 和 Agent 共用同一套 26 个工具列表。等 chat route 切到 SandboxProvider 后拆分。

---

## 会话中完成的代码变更

### JWT 删除

- `cococat/routes/auth.py` → 已删除
- `cococat/routes/ws.py` → 移除 JWT_SECRET、ALGORITHM、token 校验逻辑

### browser 工具扩展

- `cococat/core/tools.py` — `_browser()` 新增 click、type、get_content、scroll、execute_js、go_back 6 个操作。现支持 9 个操作
- `cococat/tests/core/test_browser.py` — 新增 8 个测试（12 个通过）
- 所有 action 支持可选 `url` 字段，单次调用内导航 + 操作

### pyproject.toml 补全

- 从 2 个依赖（typer + rich）补全到 11 个（fastapi/uvicorn/pydantic/pyyaml/httpx/playwright/tavily-python/e2b/e2b-code-interpreter）

### SubAgentExecutor 注入启动流程

- `cococat/__main__.py:_load_agents_from_db()` — 启动时创建 SandboxProvider + SubAgentExecutor，通过 `create_core_tools(sub_agent_executor=...)` 注入给 Agent
- 结果：sub_agent 和 dispatch_task 两个工具现在可以真实执行，不再是 stub

### cron 后台调度器

- `cococat/core/cron_worker.py` — 新建，轮询 `runs/cron/` 目录，解析 cron 表达式 / 自然语言调度，按间隔调度执行
- `cococat/app.py` — lifespan 中启动 CronWorker（与 TaskWorker 并列）
- 支持调度格式：`every 5 minutes`、`daily`、`*/15 * * * *` 等
- `cococat/tests/core/test_cron.py` — 18 个测试（3 工具 + 11 解析 + 4 Worker）全部通过

### 前端 DAG 图可视化

- `web-ui/src/components/DagGraph.tsx` — 使用 dagre + d3 的 DAG 图组件，stage/任务节点 + 依赖箭头 + 状态颜色
- `web-ui/src/pages/Dag.tsx` — 增加列表/图形双视图切换

---

## 当前代码实际状态

### 工具清单（26 个，全部真实实现）

| 工具 | 状态 | 说明 |
|------|------|------|
| read_file | 真实 | 读文件，支持 offset/limit |
| write_file | 真实 | 写文件，自动创建父目录 |
| edit_file | 真实 | 字符串替换编辑 |
| list_dir | 真实 | 列目录，按字母排序 |
| bash | 真实 | subprocess.run，30s 超时 |
| glob | 真实 | glob.glob 递归匹配 |
| grep | 真实 | 调用系统 grep -rn |
| web_search | 真实 | Tavily 集成，需 API key |
| web_fetch | 真实 | httpx GET，截断 5000 字符 |
| browser | 真实 | Playwright，9 个操作（navigate/get_text/get_content/screenshot/click/type/scroll/execute_js/go_back） |
| sub_agent | 条件 | 注入 executor 才真实，否则返回提示 |
| define_dag | 真实 | 解析 YAML，创建 runs/<id>/dag.yaml |
| append_stage | 真实 | 追加 stage 到已有 dag.yaml |
| update_dag | 真实 | dot-path 更新 dag.yaml 节点 |
| dispatch_task | 条件 | 需 sub_agent_executor 注入，标记 task 状态 + 调用 executor |
| check_tasks | 真实 | 遍历 runs/ 目录读 dag.yaml |
| stop_task | 真实 | 写取消标记文件 |
| todo_write | 真实 | 写 todos.json |
| recall | 真实 | 搜索 memory.md + memory/experiences/ |
| pin | 真实 | 追加到 memory.md |
| unpin | 真实 | 从 memory.md 移除匹配行 |
| record_experience | 真实 | 写 memory/experiences/<分类>/ |
| recall_experience | 真实 | 读 memory/experiences/<分类>/ |
| cron | 真实 | 写 JSON 到 runs/cron/（无后台调度器） |
| current_status | 真实 | 返回 agent 运行时信息 |
| wait | 真实 | asyncio.sleep() |

### 核心组件状态

| 组件 | 状态 | 文件 |
|------|------|------|
| AgentPool | 完整实现，被 chat route 使用 | cococat/core/agent_pool.py |
| SandboxProvider | 完整实现，未接入 chat route | cococat/core/sandbox/__init__.py |
| LocalExecutor | 完整实现，进程内执行 | cococat/core/sandbox/__init__.py |
| CubeSandbox | CubeSandboxExecutor 已实现（第 195-270 行），依赖 e2b SDK | cococat/core/sandbox/__init__.py |
| SceneKeeper | 完整实现 | cococat/core/scene_keeper.py |
| SubAgentExecutor | 完整实现，Pool/Sandbox 双模式，未接入 chat route | cococat/core/sub_agent.py |
| DAG 工具 | 全部真实实现 | cococat/core/tools.py |
| DAG API 路由 | 已有 | cococat/routes/dag.py |
| JWT/Auth | 已删除 | — |

### 真缺口（代码不存在，需要补）

| 缺口 | 严重性 | 说明 |
|------|--------|------|
| pyproject.toml 依赖声明 | ~~严重~~ 已修复 | ✅ 从 2 个补全到 11 个依赖 |
| cron 后台调度器 | ~~高~~ 已修复 | ✅ CronWorker 已实现（cococat/core/cron_worker.py），18 测试通过 |
| sub_agent executor 注入 | ~~高~~ 已修复 | ✅ SubAgentExecutor 已在 __main__.py 启动流程中注入 |
| 前端 DAG 可视化 | ~~中~~ 已修复 | ✅ DagGraph 组件已实现（dagre + d3），列表/图形双视图 |

### 与架构脑暴文档的矛盾（已确认）

| 矛盾点 | 文档说法 | 代码实际 | 本次决策 |
|--------|---------|---------|---------|
| AgentPool | 不存在 | 存在且活跃 | 保留过渡，Phase 3 后去掉 |
| status.yaml | 存在 | 不存在 | 删文档概念 |
| RunRecorder | 存在 | 不存在 | 删文档概念 |
| 简单任务不走 DAG | 有 | dispatch_task 强依赖 DAG | 一切皆 DAG |
| JWT/Auth | 待定 | 当时存在 | 已删除 |
| browser 操作数 | — | 仅 3 个 | 已补全到 9 个 |
| 工具数量 | 说 22 个全部真实 | 实际 26 个（24 真 + 2 条件） | 以代码为准 |
| CubeSandbox | ❌ 未做 | 已实现 | 代码已有，仅文档落后 |

---

## 后续执行计划

### 立即（P1）

| 任务 | 说明 |
|------|------|
| pyproject.toml 补全依赖 | 当前仅 typer/rich，需补 fastapi/uvicorn/pyyaml/httpx/playwright/tavily-python/e2b 等 |
| 安装 Playwright | `pip install playwright && playwright install chromium` |
| 配置 Tavily key | 设置 `TAVILY_API_KEY` 环境变量，安装 `tavily-python` |
| sub_agent executor 注入启动流程 | `__main__.py` 实例化 SubAgentExecutor，传入 Agent 工具上下文。让 sub_agent + dispatch_task 可用 |

### 短期（P2）

| 任务 | 说明 | 状态 |
|------|------|------|
| web_search 配通 | 设置 `TAVILY_API_KEY` 环境变量即可 | ⏳ 代码就绪，缺环境变量 |
| 前端 DAG 可视化 | 实时 DAG 图渲染（dagre + d3），列表/图形双视图 | ✅ 已完成 |
| cron 后台调度器 | CronWorker 轮询 runs/cron/，解析调度，执行任务 | ✅ 已完成 |

### Phase 3（P3）

| 任务 | 说明 | 依赖 |
|------|------|------|
| CubeSandbox 部署 | CubeSandboxExecutor 代码已实现（cococat/core/sandbox/__init__.py:195），需部署后端 CubeSandbox 实例 + e2b SDK | 独立部署 |
| 临时 Agent 模型 | 去掉 AgentPool，chat route 切到 SandboxProvider | CubeSandbox 部署 |
| 工具权限分离 | Main AI 和 Agent 两套工具清单 | 临时 Agent 模型 |

### 测试覆盖

- `cococat/tests/` — 95 个测试全部通过（含 CubeSandbox、browser、DAG、SceneKeeper 等）
- `tests/` — 57 个测试未在本次会话中运行
- 新增 browser 测试 8 个，全部通过
