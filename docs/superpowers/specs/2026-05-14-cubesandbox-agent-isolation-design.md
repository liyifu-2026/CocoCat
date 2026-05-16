# CubeSandbox Sub-Agent 隔离设计

日期: 2026-05-14
状态: 已确认

## 目标

Sub-Agent 被 dispatch_task 触发时，整个执行环境跑在 CubeSandbox MicroVM 中。Main AI 不受影响。

## 设计决策

| 决策 | 选择 |
|------|------|
| 方案 | **混合**：Agent ReAct 循环宿主机，执行工具全进沙箱 |
| 沙箱分配 | **一沙箱一 Sub-Agent**，即用即毁 |
| 进沙箱工具 | bash, write_file, edit_file, read_file, glob, grep, browser |
| 宿主机工具 | web_search, web_fetch, pin, unpin, recall, define_dag 等 |

## 架构

```
Main AI dispatch_task → SubAgentExecutor.dispatch()
  → sandbox_provider.run_once(prompt, tools, on_event)
    │
    ├─ CubeSandboxExecutor.create()
    │     → AsyncSandbox.create(template)  ← 60ms 冷启动
    │     → 返回 Sandbox(id, ...)
    │
    ├─ CubeSandboxExecutor.run()
    │     → 在宿主机创建 Agent (和现在一样)
    │     → tools 分两半：
    │         EXEC_TOOLS → 通过 sandbox_run 进 MicroVM
    │         HOST_TOOLS → 在宿主机直接执行
    │     → Agent.run(prompt) → ReAct 循环
    │     → 返回 result
    │
    └─ CubeSandboxExecutor.destroy()
          → sbx.kill()
```

Main AI 流程完全不变。

## 工具拆分

```python
EXEC_TOOLS = {"bash", "write_file", "edit_file", "read_file", "glob", "grep", "browser"}
HOST_TOOLS = {"web_search", "web_fetch", "pin", "unpin", "recall",
              "record_experience", "recall_experience", "define_dag",
              "append_stage", "update_dag", "dispatch_task", "check_tasks",
              "stop_task", "todo_write", "cron", "current_status", "wait"}
```

`create_core_tools()` 接收 `sandbox_run` 参数，EXEC_TOOLS 的闭包里注入 `sandbox_run`，HOST_TOOLS 不走沙箱。

`sandbox_run` 实现：在 CubeSandbox MicroVM 中执行 Python 代码段，返回 stdout。

## 文件系统

沙箱通过 code-interpreter 模板自带临时文件系统（writable-layer 1G），不需要挂载宿主机目录。

read_file / write_file 走沙箱意味着 Agent 只能访问沙箱内的文件。工作目录隔离，不会污染宿主机。

如需访问宿主机项目文件，后续可扩展为沙箱挂载特定目录。

## CubeSandboxExecutor 改造

当前 `run()` 只调 `sbx.run_code(code)`。改为创建完整 Agent：

```python
async def run(self, sandbox, task, on_event):
    tools = create_core_tools(sandbox_run=self._sandbox_run_wrapper)
    agent = Agent(id="...", role=SUB, llm=..., tools=tools)
    return await agent.run(prompt, on_text=..., on_tool=...)
```

sandbox_run_wrapper = `async def(code) → sbx.run_code(code).logs.stdout`

## CLI 行为

```
python -m cococat                           # 宿主机模式 (LocalExecutor)
python -m cococat --cube-sandbox            # Sub-Agent 隔离模式
```

## 改动清单

| 文件 | 改动 |
|------|------|
| `core/sandbox/cubesandbox.py` | 重写 `run()` 为创建 Agent + ReAct；新增 `_sandbox_run`、`_resolve_llm`、`_make_sandbox_run`、`_wrap_exec_tools`、`_tool_to_code` |
| `__main__.py` | `--cube-sandbox` 时用 `CubeSandboxExecutor` 替代 `LocalExecutor` |
| `tests/core/test_cubesandbox_executor.py` | 新建 6 个测试（Agent 执行、session 持久化、sandbox_run wrapper） |
| `tests/core/test_cube_sandbox.py` | 更新旧测试适配新 `run()` 语义 |

## 当前模板

使用已有 code-interpreter 模板 `tpl-dedcd9373c3f49939f7feb9b`，包含 Python 3.12 + 基础库，满足所有工具执行需求。

## 不做

- Main AI 进沙箱 — 它没有执行工具
- 沙箱挂载宿主机目录 — 当前用沙箱自带临时文件系统
- DAG 强制执行 — 后续单独处理
