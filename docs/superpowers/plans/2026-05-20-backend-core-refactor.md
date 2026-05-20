# CocoCat 后端核心重构 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 CocoCat 后端从「AgentPool + DAG 多 Agent 架构」重构为「Coco 单智能体 + Mode 人格 + sub_agent 工具 + Scene 房间」的极简模型。

**Architecture:** 移除 AgentPool、DAG 系统、Agent 模板表。引入 Mode YAML 配置系统。统一所有 Agent 执行路径为 `ExecutorProvider.run_once()`。Session 和 Memory 按 Scene×User 隔离存储。

**Tech Stack:** Python 3.10+, FastAPI, SQLite, pytest + pytest-asyncio, YAML

**参考规格:** `docs/superpowers/specs/2026-05-20-core-model-analysis.md`

---

## 文件变更总览

### 创建
| 文件 | 说明 |
|------|------|
| `config/modes/default.yaml` | 主人格 Mode 定义 |
| `config/modes/kb-admin.yaml` | 知识库管理 Mode 定义 |
| `config/cron.yaml` | 系统级 cron 任务定义 |
| `cococat/core/modes.py` | Mode 加载器 |

### 修改
| 文件 | 改动 |
|------|------|
| `cococat/core/sandbox/__init__.py` | 重命名 SandboxProvider → ExecutorProvider |
| `cococat/core/sandbox/local_executor.py` | 重命名 LocalExecutor → InProcessExecutor |
| `cococat/core/sandbox/__init__.py` | 导出 InProcessExecutor |
| `cococat/core/bootstrap.py` | 砍 AgentPool 引用，引入 Mode，改 cron |
| `cococat/core/sub_agent.py` | 砍 _dispatch_via_pool，简化 dispatch |
| `cococat/core/tools/__init__.py` | ToolCatalog 退化为注册表 |
| `cococat/core/worker.py` | 砍 _process_dag + _check_run_completion |
| `cococat/core/agent.py` | 删除 DAG 引用，引入 Mode |
| `cococat/core/agent_builder/prompt.py` | 删 COCO_BEHAVIOR_RULES 常量 |
| `cococat/core/cron_worker.py` | 砍 AgentPool 依赖，改用 ExecutorProvider |
| `cococat/core/scene_keeper.py` | 砍 agent 查找，直接调用 Coco |
| `cococat/core/cron_tasks.py` | 适配新模式 |
| `cococat/context.py` | 砍 AgentPool + DagStore 字段 |
| `cococat/app.py` | 砍 AgentPool 创建 + DagStore 注入 |
| `cococat/db/database.py` | SCHEMA 删 agents/dag_runs/tasks 表，改 scenes 表 |
| `cococat/routes/chat.py` | 加 mode 参数，砍 DAG 引用 |
| `cococat/routes/scenes.py` | 砍 agent 创建逻辑 |
| `cococat/routes/ws.py` | 砍 DAG 事件推送 |
| `cococat/routes/knowledge.py` | ingest 改为交给 Coco |
| `cococat/routes/cron.py` | 适配 mode |
| `cococat/__main__.py` | 适配新参数 |

### 删除
| 文件 | 说明 |
|------|------|
| `cococat/core/agent_pool.py` | 整个文件 |
| `cococat/core/tools/dag.py` | 整个文件 |
| `cococat/dag/store.py` | 整个文件 |
| `cococat/dag/executor.py` | 整个文件 |
| `cococat/dag/__init__.py` | 整个文件 |
| `cococat/db/agent_store.py` | 整个文件 |
| `cococat/db/dag_run_store.py` | 整个文件 |
| `cococat/db/task_store.py` | 整个文件 |
| `cococat/routes/agents.py` | 整个文件 |
| `cococat/routes/dag.py` | 整个文件 |
| `config/residents/coco.yaml` | 废弃 |
| `config/residents/kb-agent.yaml` | 废弃 |

---

## Phase 0：预备——创建 Mode 配置 + Mode 加载器

### Task 0.1：创建 Mode YAML 文件

**Files:**
- Create: `config/modes/default.yaml`
- Create: `config/modes/kb-admin.yaml`

- [ ] **Step 1: 创建默认 Mode 配置**

```yaml
# config/modes/default.yaml
id: default
name: Coco
description: "通用主人格，处理日常对话、任务调度和大多数工作场景"
system_prompt: |
  你是 Coco，CocoCat 平台的核心智能体。你的职责是理解用户需求、拆解任务、并调度工具来完成任务。

  ## 核心规则
  1. 始终以用户的目标为中心思考
  2. 复杂任务可以调用 sub_agent 工具来并行处理
  3. 需要操作知识库时，系统会自动切换到 kb-admin 模式
  4. 保持回复简洁、温暖、专业

  ## 可用能力
  - 对话和问答
  - 调用 sub_agent 执行具体任务（文件读写、代码执行、网页搜索等）
  - 查阅知识库
  - 管理记忆（pin/recall）

tools:
  - sub_agent
  - read_file
  - list_dir
  - glob
  - grep
  - web_search
  - web_fetch
  - search_kb
  - read_wiki
  - list_kbs
  - pin
  - unpin
  - recall
  - cron
  - current_status

skills: []
```

- [ ] **Step 2: 创建 kb-admin Mode 配置**

```yaml
# config/modes/kb-admin.yaml
id: kb-admin
name: 知识库管理
description: "知识库管理模式，用于文件摄入、索引、去重和质量维护"
system_prompt: |
  你是 Coco，当前在知识库管理模式下工作。你的职责是管理知识库：摄入文档、建立索引、检测重复、维护内容质量。

  ## 核心规则
  1. 收到文件后，仔细阅读并提取结构化信息
  2. 将内容写入合适的 wiki 页面
  3. 定期检查知识库健康（lint、dedup）
  4. 保持知识库组织清晰、易于检索

  ## 可用能力
  - 读写文件
  - 执行 bash 命令（用于 ingest 管道）
  - 管理 wiki 页面
  - 调用 sub_agent 并行处理多个文件

tools:
  - sub_agent
  - read_file
  - write_file
  - edit_file
  - list_dir
  - glob
  - grep
  - bash
  - web_search
  - web_fetch
  - search_kb
  - read_wiki
  - write_wiki
  - list_kbs
  - run_lint
  - run_dedup
  - gen_overview
  - pin
  - unpin
  - recall
  - cron
  - current_status

skills:
  - knowledge-ingestion
```

- [ ] **Step 3: 创建系统 cron 配置**

```yaml
# config/cron.yaml
tasks:
  - name: kb-lint
    schedule: "@daily"
    at_time: "03:00"
    mode: kb-admin
    task: "对所有知识库运行 lint 检查，报告孤立页面和损坏链接"
    
  - name: kb-dedup  
    schedule: "@weekly"
    mode: kb-admin
    task: "检测并合并所有知识库中的重复内容"
    
  - name: kb-overview
    schedule: "@weekly"
    mode: kb-admin
    task: "生成所有知识库内容的全局概览"

  - name: memory-dream
    schedule: "@daily"
    at_time: "02:00"
    mode: default
    scene_scope: all
    task: "对所有 Scene 的会话进行 dream 提取和记忆编译"
```

- [ ] **Step 4: Commit**

```bash
git add config/modes/ config/cron.yaml
git commit -m "feat: add Mode YAML configs and system cron definition"
```

### Task 0.2：创建 Mode 加载器

**Files:**
- Create: `cococat/core/modes.py`
- Test: `tests/core/test_modes.py`

- [ ] **Step 1: 编写测试**

```python
# tests/core/test_modes.py
import pytest
from cococat.core.modes import load_mode, list_modes, ModeConfig


def test_load_default_mode():
    mode = load_mode("default")
    assert mode.id == "default"
    assert mode.name == "Coco"
    assert "sub_agent" in mode.tools
    assert "你是 Coco" in mode.system_prompt


def test_load_kb_admin_mode():
    mode = load_mode("kb-admin")
    assert mode.id == "kb-admin"
    assert "write_file" in mode.tools
    assert "bash" in mode.tools
    assert "知识库管理" in mode.name


def test_list_modes():
    modes = list_modes()
    assert len(modes) >= 2
    ids = [m.id for m in modes]
    assert "default" in ids
    assert "kb-admin" in ids


def test_load_nonexistent_mode():
    with pytest.raises(FileNotFoundError):
        load_mode("nonexistent")


def test_mode_config_immutability():
    mode = load_mode("default")
    with pytest.raises(Exception):
        mode.tools.append("extra")  # tools should be tuple or not writable
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/core/test_modes.py -v
# Expected: FAIL — ModuleNotFoundError: No module named 'cococat.core.modes'
```

- [ ] **Step 3: 实现 Mode 加载器**

```python
# cococat/core/modes.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

MODES_DIR = Path(__file__).parent.parent.parent / "config" / "modes"


@dataclass(frozen=True)
class ModeConfig:
    id: str
    name: str
    description: str
    system_prompt: str
    tools: tuple[str, ...]
    skills: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "skills", tuple(self.skills))


def load_mode(mode_id: str) -> ModeConfig:
    path = MODES_DIR / f"{mode_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Mode '{mode_id}' not found at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return ModeConfig(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        system_prompt=data["system_prompt"],
        tools=data.get("tools", []),
        skills=data.get("skills", []),
    )


def list_modes() -> list[ModeConfig]:
    modes = []
    for p in MODES_DIR.glob("*.yaml"):
        mode_id = p.stem
        try:
            modes.append(load_mode(mode_id))
        except Exception:
            continue
    return modes
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/core/test_modes.py -v
# Expected: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add cococat/core/modes.py tests/core/test_modes.py
git commit -m "feat: add Mode config loader"
```

---

## Phase 1：砍 AgentPool + 统一执行路径

### Task 1.1：重命名 SandboxProvider → ExecutorProvider

**Files:**
- Modify: `cococat/core/sandbox/__init__.py`
- Modify: `cococat/core/sandbox/local_executor.py`
- Test: `tests/core/sandbox/test_sandbox.py`

- [ ] **Step 1: 重命名 LocalExecutor → InProcessExecutor**

```python
# cococat/core/sandbox/local_executor.py — 修改类名
class InProcessExecutor:  # was: LocalExecutor
    """In-process agent executor — development mode, no hardware isolation."""
    # ... rest unchanged
```

- [ ] **Step 2: 重命名 SandboxProvider → ExecutorProvider**

```python
# cococat/core/sandbox/__init__.py — 修改类名
class ExecutorProvider:  # was: SandboxProvider
    """Unified agent execution provider.
    
    Routes all agent runs through a single executor (InProcessExecutor 
    or CubeSandboxExecutor depending on --cube-sandbox flag).
    """
    def __init__(self, executor=None):
        if executor is None:
            from cococat.core.sandbox.local_executor import InProcessExecutor
            executor = InProcessExecutor()
        self._executor = executor
    # ... rest unchanged, method names stay the same
```

- [ ] **Step 3: 更新 `__init__.py` 导出**

```python
# cococat/core/sandbox/__init__.py
from cococat.core.sandbox.sandbox import Sandbox
from cococat.core.sandbox.local_executor import InProcessExecutor
from cococat.core.sandbox.cubesandbox import CubeSandboxExecutor

__all__ = ["Sandbox", "ExecutorProvider", "InProcessExecutor", "CubeSandboxExecutor"]
```

- [ ] **Step 4: 运行 sandbox 测试**

```bash
python -m pytest tests/core/sandbox/ -v
# Expected: all pass after import updates
```

- [ ] **Step 5: Commit**

```bash
git add cococat/core/sandbox/
git commit -m "refactor: rename SandboxProvider→ExecutorProvider, LocalExecutor→InProcessExecutor"
```

### Task 1.2：从 context.py 移除 AgentPool 和 DagStore

**Files:**
- Modify: `cococat/context.py`

- [ ] **Step 1: 修改 AppContext**

```python
# cococat/context.py — 移除 AgentPool 和 DagStore 引用
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cococat.db.database import Database
    from cococat.core.event_bus import EventBus
    from cococat.core.sub_agent import SubAgentExecutor
    from cococat.core.sandbox import ExecutorProvider
    from cococat.config_store import ConfigStore
    from cococat.core.channel_manager import ChannelManager
    from cococat.routes.ws import WsManager
    from cococat.auth import CredentialManager
    from cococat.providers.base import ProviderFactory


@dataclass
class AppContext:
    db: Database | None = None
    bus: EventBus | None = None
    sandbox: ExecutorProvider | None = None  # was: sandbox_provider
    sub_executor: SubAgentExecutor | None = None
    config_store: ConfigStore | None = None
    creds: CredentialManager | None = None
    provider_factory: ProviderFactory | None = None
    channel_manager: ChannelManager | None = None
    ws_manager: WsManager | None = None
```

- [ ] **Step 2: 更新所有 context 引用**

```bash
# 查找所有引用 AgentPool 或 DagStore 或 pool 的地方
rg "ctx\.pool|ctx\.dag_store|from cococat.core.agent_pool" cococat/ --files-with-matches
```

预期输出涉及文件：`app.py`, `worker.py`, `bootstrap.py`, `cron_worker.py`, `sub_agent.py`——这些将在后续任务中逐一修改。此处仅确认列表。

- [ ] **Step 3: Commit**

```bash
git add cococat/context.py
git commit -m "refactor: remove AgentPool and DagStore from AppContext"
```

### Task 1.3：删除 AgentPool 文件并更新所有 import

**Files:**
- Delete: `cococat/core/agent_pool.py`
- Modify: 所有 import AgentPool 的文件
- Test: `tests/core/test_agent_pool.py`（删除）

- [ ] **Step 1: 删除 agent_pool.py 和它的测试**

```bash
rm cococat/core/agent_pool.py
rm tests/core/test_agent_pool.py
```

- [ ] **Step 2: 更新 `cococat/app.py` 移除 AgentPool 创建**

```python
# cococat/app.py — 移除 AgentPool import 和创建
# 删除: from cococat.core.agent_pool import AgentPool
# 删除: pool = AgentPool(bus)
# 修改 lifespan: 不再向 TaskWorker/CronWorker 传 pool
```

- [ ] **Step 3: 更新 `cococat/core/sub_agent.py` 移除 AgentPool 依赖**

```python
# cococat/core/sub_agent.py — 移除 pool 参数和 _dispatch_via_pool
from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from cococat.core.event_bus import EventBus
    from cococat.core.sandbox import ExecutorProvider


class SubAgentExecutor:
    def __init__(self, bus: EventBus | None = None, sandbox: ExecutorProvider | None = None):
        self._bus = bus
        self._sandbox = sandbox

    async def dispatch(self, task: str, from_agent: str = "main",
                       session_id: str | None = None,
                       mode: str = "default") -> str | None:
        if self._sandbox is None:
            raise RuntimeError("SubAgentExecutor has no ExecutorProvider")
        task_id = str(uuid.uuid4())[:8]
        return await self._dispatch(task, task_id, from_agent, session_id, mode)

    async def _dispatch(self, task: str, task_id: str, from_agent: str,
                        session_id: str | None, mode: str) -> str | None:
        agent_id = f"sub-{task_id}"
        result = await self._sandbox.run_once(
            prompt=task,
            agent_id=agent_id,
            session_id=session_id,
            mode=mode,
        )
        if self._bus:
            await self._bus.publish("sub_agent_complete", {
                "task_id": task_id,
                "from_agent": from_agent,
                "result": result,
            })
        return result

    async def get_pending_tasks(self) -> list[str]:
        return []
```

- [ ] **Step 4: 更新 `cococat/core/cron_worker.py` 移除 AgentPool 依赖**

```python
# cococat/core/cron_worker.py — 移除 AgentPool import，改用 ExecutorProvider
# 删除: from cococat.core.agent_pool import AgentPool
# 修改 __init__: 移除 pool 参数，添加 sandbox 参数

class CronWorker:
    def __init__(self, sandbox: "ExecutorProvider", sub_executor: "SubAgentExecutor | None" = None,
                 poll_interval: float = 30.0, cron_dir: str | None = None):
        self._sandbox = sandbox
        self._sub_executor = sub_executor
        self._poll_interval = poll_interval
        self._cron_dir = cron_dir
        # ...

    async def _dispatch(self, task: str, target_mode: str, scene_id: str | None = None):
        """Dispatch a cron task via ExecutorProvider."""
        return await self._sandbox.run_once(
            prompt=task,
            agent_id="cron",
            mode=target_mode,
            scene_id=scene_id,
        )
```

- [ ] **Step 5: 更新 `cococat/worker.py` 移除 AgentPool 引用**

```python
# cococat/worker.py — 移除 AgentPool import 和 self._pool 相关代码
# 删除: from cococat.core.agent_pool import AgentPool
# 修改 __init__: 移除 pool 参数
# 修改 set_dag_store → 删除整个方法
# 删除 _process_dag 方法
# 删除 _check_run_completion 方法
```

- [ ] **Step 6: 更新 `cococat/core/bootstrap.py` 移除 AgentPool 引用**

```python
# cococat/core/bootstrap.py — 关键改动
# 删除所有 AgentPool 创建和使用
# _load_residents → 不再创建 Agent 对象，改为仅验证 Mode 配置存在
# _load_workers → 删除整个函数
```

- [ ] **Step 7: Commit**

```bash
git rm cococat/core/agent_pool.py tests/core/test_agent_pool.py
git add cococat/core/sub_agent.py cococat/core/cron_worker.py cococat/worker.py cococat/core/bootstrap.py cococat/app.py
git commit -m "refactor: remove AgentPool, unify execution via ExecutorProvider"
```

### Task 1.4：更新 ExecutorProvider.run_once 支持 mode 参数

**Files:**
- Modify: `cococat/core/sandbox/__init__.py`

- [ ] **Step 1: 修改 run_once 签名**

```python
# cococat/core/sandbox/__init__.py — ExecutorProvider.run_once
async def run_once(self, prompt: str, agent_id: str = "coco",
                   permissions: dict | None = None,
                   tools: list | None = None,
                   on_event: callable | None = None,
                   session_id: str | None = None,
                   mode: str = "default",
                   scene_id: str | None = None,
                   user_id: str | None = None) -> str:
    sandbox_id = self.create(template=None, permissions=permissions)
    try:
        return await self.run(sandbox_id, task=prompt, on_event=on_event,
                             tools=tools, agent_id=agent_id,
                             session_id=session_id, mode=mode,
                             scene_id=scene_id, user_id=user_id)
    finally:
        self.destroy(sandbox_id)


async def run(self, sandbox_id: str, task: str,
              on_event: callable | None = None,
              tools: list | None = None,
              agent_id: str = "coco",
              session_id: str | None = None,
              mode: str = "default",
              scene_id: str | None = None,
              user_id: str | None = None) -> str:
    sandbox = self._sandboxes[sandbox_id]
    return await self._executor.run(
        sandbox, task, on_event=on_event, tools=tools,
        agent_id=agent_id, session_id=session_id,
        mode=mode, scene_id=scene_id, user_id=user_id,
    )
```

- [ ] **Step 2: 更新 InProcessExecutor.run 支持新参数**

```python
# cococat/core/sandbox/local_executor.py — InProcessExecutor.run
async def run(self, sandbox: Sandbox, task: str,
              on_event=None, tools=None, agent_id="coco",
              session_id=None, mode="default",
              scene_id=None, user_id=None):
    async with self._semaphore:
        return await self._do_run(sandbox, task, on_event, tools,
                                  agent_id, session_id, mode,
                                  scene_id, user_id)

async def _do_run(self, sandbox, task, on_event, tools,
                  agent_id, session_id, mode, scene_id, user_id):
    if tools is None:
        tools = self._resolve_tools_for_mode(mode)
    return await _make_and_run_agent(
        agent_id=agent_id, prompt=task, tools=tools,
        resolve_llm=self._resolve_llm, session_id=session_id,
        on_event=on_event, agents_dir=self._resolve_agents_dir(scene_id, user_id),
        mode=mode, scene_id=scene_id, user_id=user_id,
    )

def _resolve_tools_for_mode(self, mode: str) -> list:
    """Resolve tools for a given mode from ToolCatalog registry."""
    from cococat.core.tools import resolve_tools_for_mode
    return resolve_tools_for_mode(mode)

def _resolve_agents_dir(self, scene_id: str | None, user_id: str | None) -> str:
    """Resolve session storage directory: scenes/{id}/sessions/{user_id}/"""
    if scene_id and user_id:
        return f"scenes/{scene_id}/sessions/{user_id}"
    elif scene_id:
        return f"scenes/{scene_id}/sessions"
    return "sessions/default"
```

- [ ] **Step 3: Commit**

```bash
git add cococat/core/sandbox/
git commit -m "feat: add mode/scene/user params to ExecutorProvider.run_once"
```

---

## Phase 2：ToolCatalog 退化 + System Prompt 重构 + DAG 工具删除

### Task 2.1：删除 DAG 工具文件和相关 import

**Files:**
- Delete: `cococat/core/tools/dag.py`
- Delete: `cococat/dag/store.py`
- Delete: `cococat/dag/executor.py`
- Delete: `cococat/dag/__init__.py`
- Modify: `cococat/core/tools/__init__.py`

- [ ] **Step 1: 删除 DAG 文件**

```bash
rm cococat/core/tools/dag.py
rm -rf cococat/dag/
```

- [ ] **Step 2: 重构 ToolCatalog 为纯注册表**

```python
# cococat/core/tools/__init__.py — 退化为工具注册表
from cococat.core.tools.file_ops import make_file_tools, make_readonly_file_tools
from cococat.core.tools.execution import make_execution_tools
from cococat.core.tools.web import make_web_tools
from cococat.core.tools.memory_tools import make_memory_tools
from cococat.core.tools.kb_tools import make_kb_tools, make_kb_admin_tools
from cococat.core.tools.meta import make_meta_tools

_ALL_TOOLS = {
    # file ops
    "read_file": lambda: make_readonly_file_tools()[0],
    "write_file": lambda: make_file_tools()[1],
    "edit_file": lambda: make_file_tools()[2],
    "list_dir": lambda: make_readonly_file_tools()[1],
    "glob": lambda: make_readonly_file_tools()[2],
    "grep": lambda: make_readonly_file_tools()[3],
    # execution
    "bash": lambda sandbox_run=None: make_execution_tools(sandbox_run)[0],
    "browser": lambda sandbox_run=None: make_execution_tools(sandbox_run)[1],
    # web
    "web_search": lambda tavily_key=None: make_web_tools(tavily_key)[0],
    "web_fetch": lambda tavily_key=None: make_web_tools(tavily_key)[1],
    # memory
    "pin": lambda: make_memory_tools()[0],
    "unpin": lambda: make_memory_tools()[1],
    "recall": lambda: make_memory_tools()[2],
    # kb
    "search_kb": lambda: make_kb_tools()[0],
    "read_wiki": lambda: make_kb_tools()[1],
    "write_wiki": lambda: make_kb_tools()[2],
    "list_kbs": lambda: make_kb_tools()[3],
    # kb admin
    "run_lint": lambda: make_kb_admin_tools()[0],
    "run_dedup": lambda: make_kb_admin_tools()[1],
    "gen_overview": lambda: make_kb_admin_tools()[2],
    # meta
    "cron": lambda: make_meta_tools()[0],
    "wait": lambda: make_meta_tools()[1],
    "current_status": lambda: make_meta_tools()[2],
}


def resolve_tools_for_mode(mode_id: str,
                           sandbox_run=None,
                           tavily_api_key=None,
                           sub_agent_executor=None) -> list:
    """Resolve tools for a given mode from the mode's tool list."""
    from cococat.core.modes import load_mode
    mode = load_mode(mode_id)
    tools = []
    for tool_name in mode.tools:
        if tool_name == "sub_agent" and sub_agent_executor:
            tools.append(_make_sub_agent_tool(sub_agent_executor))
        elif tool_name in _ALL_TOOLS:
            factory = _ALL_TOOLS[tool_name]
            try:
                if tool_name in ("bash", "browser"):
                    tool = factory(sandbox_run=sandbox_run)
                elif tool_name in ("web_search", "web_fetch"):
                    tool = factory(tavily_key=tavily_api_key)
                else:
                    tool = factory()
                if isinstance(tool, list):
                    tools.extend(tool)
                else:
                    tools.append(tool)
            except Exception:
                continue
    return tools


def _make_sub_agent_tool(sub_agent_executor) -> "Tool":
    from cococat.core.tools.types import Tool, _make
    return Tool(
        name="sub_agent",
        description="Fork a temporary worker to execute a task in parallel. "
                    "Use for complex, independent sub-tasks. "
                    "Parameters: prompt (task description), mode (optional, default inherits current mode)",
        function=_make(lambda prompt, mode=None, ctx=None:
                       sub_agent_executor(prompt)),
    )
```

- [ ] **Step 3: 删除旧 factory 函数**

从 `__init__.py` 删除：`create_core_tools`, `create_main_ai_tools`, `create_resident_tools` 及 `ToolCatalog` 类。

- [ ] **Step 4: Commit**

```bash
git rm cococat/core/tools/dag.py cococat/dag/
git add cococat/core/tools/__init__.py
git commit -m "refactor: remove DAG system, simplify ToolCatalog to registry"
```

### Task 2.2：清理 System Prompt 常量

**Files:**
- Modify: `cococat/core/agent_builder/prompt.py`

- [ ] **Step 1: 删除 Python 常量**

```python
# cococat/core/agent_builder/prompt.py — 删除 COCO_BEHAVIOR_RULES, KB_AGENT_BEHAVIOR_RULES
# 删除 STATIC_PREFIX, KB_AGENT_STATIC_PREFIX 别名

# 保留函数 build_system_prompt，但改为从 Mode 加载 prompt
def build_system_prompt(mode_id: str = "default",
                        scene_context: str | None = None,
                        scene_kbs: list | None = None,
                        scene_skills: list | None = None,
                        memory_content: str | None = None,
                        pinned_facts: str | None = None,
                        compiled_content: str | None = None,
                        tools: list | None = None) -> str:
    from cococat.core.modes import load_mode
    mode = load_mode(mode_id)
    parts = [mode.system_prompt]
    
    if scene_context:
        parts.append(f"\n## 当前场景上下文\n{scene_context}")
    if scene_kbs:
        parts.append(f"\n## 可用知识库\n" + "\n".join(f"- {kb}" for kb in scene_kbs))
    if memory_content:
        parts.append(f"\n## 记忆\n{memory_content}")
    if pinned_facts:
        parts.append(f"\n## 置顶事实\n{pinned_facts}")
    if compiled_content:
        parts.append(f"\n## 编译记忆\n{compiled_content}")
    if tools:
        from cococat.core.agent_builder.prompt import build_tool_section
        parts.append(build_tool_section(tools))
    
    return "\n\n".join(parts)
```

- [ ] **Step 2: 保留的工具函数不变**

`build_tool_section`, `load_memory_from_agent_dir`（后续改为从 Scene 目录加载）。

- [ ] **Step 3: Commit**

```bash
git add cococat/core/agent_builder/prompt.py
git commit -m "refactor: remove hardcoded prompt constants, load from Mode YAML"
```

---

## Phase 3：数据库迁移

### Task 3.1：更新 SCHEMA 删除旧表

**Files:**
- Modify: `cococat/db/database.py`

- [ ] **Step 1: 从 SCHEMA 删除 agents、dag_runs、tasks 表定义**

```python
# cococat/db/database.py — SCHEMA 常量中删除以下 CREATE TABLE 语句：
# - agents
# - dag_runs  
# - tasks
# 保留: messages, scenes, users, channel_identities, memory_fts(memory_fts 也需要重新审视，但不在此重构范围)
```

- [ ] **Step 2: 修改 scenes 表**

```python
# scenes 表改动：删除 agent_id 列
# 原: agent_id TEXT, status TEXT DEFAULT 'active', ...
# 改: 删除 agent_id, status 保留
scenes_schema = """
CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    context TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    purpose TEXT DEFAULT '',
    kbs TEXT DEFAULT '[]',
    skills TEXT DEFAULT '[]',
    tools TEXT DEFAULT '[]',
    channels TEXT DEFAULT '{}',
    llm_config TEXT DEFAULT '{}',
    visibility TEXT DEFAULT 'private',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    archived_at TEXT
)
"""
```

- [ ] **Step 3: 添加迁移 SQL 文件**

```sql
-- cococat/db/migrations/002_drop_agent_tables.sql
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS dag_runs;
DROP TABLE IF EXISTS tasks;

-- Alter scenes: drop agent_id column
-- SQLite doesn't support DROP COLUMN directly before 3.35
-- Use recreate pattern
CREATE TABLE scenes_new (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    context TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    purpose TEXT DEFAULT '',
    kbs TEXT DEFAULT '[]',
    skills TEXT DEFAULT '[]',
    tools TEXT DEFAULT '[]',
    channels TEXT DEFAULT '{}',
    llm_config TEXT DEFAULT '{}',
    visibility TEXT DEFAULT 'private',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    archived_at TEXT
);
INSERT INTO scenes_new SELECT 
    id, name, description, context, status, purpose,
    kbs, skills, tools, channels, llm_config, visibility,
    created_at, updated_at, archived_at
FROM scenes;
DROP TABLE scenes;
ALTER TABLE scenes_new RENAME TO scenes;
```

- [ ] **Step 4: 删除对应的 Store 文件**

```bash
rm cococat/db/agent_store.py
rm cococat/db/dag_run_store.py
rm cococat/db/task_store.py
```

- [ ] **Step 5: 更新 `db/__init__.py` 导出**

```python
# cococat/db/__init__.py
from cococat.db.database import Database, new_uuid
from cococat.db.scene_store import SceneStore
from cococat.db.message_store import MessageStore

__all__ = ["Database", "new_uuid", "SceneStore", "MessageStore"]
```

- [ ] **Step 6: 更新 Database 类属性**

```python
# cococat/db/database.py — Database 类
# 删除 self.agents, self.tasks, self.dag_runs 属性
# 保留 self.scenes, self.messages
```

- [ ] **Step 7: Commit**

```bash
git rm cococat/db/agent_store.py cococat/db/dag_run_store.py cococat/db/task_store.py
git add cococat/db/
git commit -m "refactor: drop agents/dag_runs/tasks tables, remove agent_id from scenes"
```

---

## Phase 4：Route 改造

### Task 4.1：删除 agents + dag 路由

**Files:**
- Delete: `cococat/routes/agents.py`
- Delete: `cococat/routes/dag.py`
- Modify: `cococat/app.py`（移除路由注册）

- [ ] **Step 1: 删除文件**

```bash
rm cococat/routes/agents.py cococat/routes/dag.py
```

- [ ] **Step 2: 更新 app.py 路由注册**

```python
# cococat/app.py — 删除 agents_router 和 dag_router 的注册
# 删除:
#   from cococat.routes import agents
#   from cococat.routes import dag
#   app.include_router(agents.router)
#   app.include_router(dag.router)
```

- [ ] **Step 3: 删除对应测试**

```bash
rm tests/routes/test_dag_api.py
# tests/core/test_dag.py 和 test_dag_integration.py 也删除
rm tests/core/test_dag.py tests/core/test_dag_integration.py tests/core/test_sqlite_dag_store.py
```

- [ ] **Step 4: Commit**

```bash
git rm cococat/routes/agents.py cococat/routes/dag.py tests/routes/test_dag_api.py tests/core/test_dag*.py tests/core/test_sqlite_dag_store.py
git add cococat/app.py
git commit -m "refactor: remove agents and dag routes"
```

### Task 4.2：修改 Chat 路由支持 mode 参数

**Files:**
- Modify: `cococat/routes/chat.py`

- [ ] **Step 1: 修改 POST /chat 添加 mode 参数**

```python
# cococat/routes/chat.py

@router.post("/chat")
async def chat(request: Request, ctx=Depends(get_ctx)):
    body = await request.json()
    content = body.get("content", "")
    scene_id = body.get("scene_id")
    mode = body.get("mode", "default")  # 新增
    session_id = body.get("session_id")
    
    # 合并 kb-chat 逻辑：如果 mode == "kb-admin" 则加载 kb 工具
    tools = resolve_tools_for_mode(
        mode,
        sandbox_run=None,  # InProcess mode
        tavily_api_key=resolve_tavily_key(ctx.config_store),
        sub_agent_executor=ctx.sub_executor.dispatch if ctx.sub_executor else None,
    )
    
    result = await ctx.sandbox.run_once(
        prompt=content,
        agent_id="coco",
        tools=tools,
        session_id=session_id,
        mode=mode,
        scene_id=scene_id,
    )
    return {"content": result}
```

- [ ] **Step 2: 合并 DELETE /kb-chat 路由到 chat 或删除**

`POST /kb-chat` 逻辑已由 mode="kb-admin" 覆盖，删除独立 kb-chat 端点。

- [ ] **Step 3: Commit**

```bash
git add cococat/routes/chat.py
git commit -m "feat: add mode param to chat route, merge kb-chat"
```

### Task 4.3：修改 Scenes 路由删 agent 绑定

**Files:**
- Modify: `cococat/routes/scenes.py`
- Modify: `cococat/routes/scene_mgmt.py`

- [ ] **Step 1: 修改 create_scene_full 不再创建 Agent**

```python
# cococat/routes/scenes.py — create_scene_full
@router.post("/full")
async def create_scene_full(request: Request, ctx=Depends(get_ctx)):
    body = await request.json()
    scene_id = body.get("name", "").lower().replace(" ", "-")
    
    # 不再创建 Agent
    ctx.db.scenes.create(
        id=scene_id,
        name=body.get("name", ""),
        description=body.get("description", ""),
        context=body.get("purpose", ""),
        kbs=json.dumps(body.get("kbs", [])),
        skills=json.dumps(body.get("skills", [])),
        channels=json.dumps(body.get("channels", {})),
    )
    return {"id": scene_id}
```

- [ ] **Step 2: 删除 roster 相关处理**

```python
# cococat/routes/scene_mgmt.py — 删除所有 roster 引用
# 确认不再读取或写入 roster 字段
```

- [ ] **Step 3: Commit**

```bash
git add cococat/routes/scenes.py cococat/routes/scene_mgmt.py
git commit -m "refactor: remove agent creation from scene creation, remove roster"
```

### Task 4.4：修改 WebSocket 路由删 DAG 事件

**Files:**
- Modify: `cococat/routes/ws.py`

- [ ] **Step 1: 删除 DAG 相关事件推送**

```python
# cococat/routes/ws.py — 删除所有 dag.completed / dag.progress 事件推送
# 保留 text_delta, stream_tool, stream_reasoning 事件
```

- [ ] **Step 2: Commit**

```bash
git add cococat/routes/ws.py
git commit -m "refactor: remove DAG events from WebSocket"
```

### Task 4.5：修改 Knowledge 路由改为交给 Coco

**Files:**
- Modify: `cococat/routes/knowledge.py`

- [ ] **Step 1: 修改文件上传逻辑**

```python
# cococat/routes/knowledge.py — upload 端点
@router.post("/{kb_name}/upload")
async def upload_file(kb_name: str, file: UploadFile, ctx=Depends(get_ctx)):
    # 保存文件到临时位置
    # 调用 Coco 在 kb-admin mode 下处理
    tools = resolve_tools_for_mode("kb-admin")
    await ctx.sandbox.run_once(
        prompt=f"请处理新上传到 {kb_name} 的文件: {file.filename}，读取内容并创建 wiki 页面",
        tools=tools,
        mode="kb-admin",
    )
    return {"status": "processing"}
```

- [ ] **Step 2: Commit**

```bash
git add cococat/routes/knowledge.py
git commit -m "refactor: route KB uploads through Coco in kb-admin mode"
```

---

## Phase 5：Scene Keeper + Cron + Bootstrap 整合

### Task 5.1：简化 SceneKeeper

**Files:**
- Modify: `cococat/core/scene_keeper.py`

- [ ] **Step 1: 砍 agent 查找**

```python
# cococat/core/scene_keeper.py — handle_message
async def handle_message(self, raw_msg: dict) -> str | None:
    # ... 解析 identity ...
    # 直接调用 ExecutorProvider，不查找 agent
    result = await self._sandbox.run_once(
        prompt=message_content,
        agent_id="coco",
        scene_id=self._scene_id,
        mode="default",
    )
    # ... send reply ...
```

- [ ] **Step 2: Commit**

```bash
git add cococat/core/scene_keeper.py
git commit -m "refactor: simplify SceneKeeper, remove agent lookup"
```

### Task 5.2：重构 Bootstrap

**Files:**
- Modify: `cococat/core/bootstrap.py`

- [ ] **Step 1: 重写 load_agents**

```python
# cococat/core/bootstrap.py
def load_agents(app, args):
    ctx = app.state.ctx
    
    # 1. 验证 Mode 配置存在
    from cococat.core.modes import list_modes
    modes = list_modes()
    if not modes:
        raise RuntimeError("No modes found in config/modes/")
    print(f"Loaded {len(modes)} modes: {[m.id for m in modes]}")
    
    # 2. 设置 Provider
    _setup_providers(ctx, args.auth)
    
    # 3. 设置 Sandbox (现在叫 Executor)
    _setup_executor(ctx, ctx.provider_factory, args)
    
    # 4. 设置 SubAgentExecutor（无需 pool）
    ctx.sub_executor = SubAgentExecutor(bus=ctx.bus, sandbox=ctx.sandbox)
    
    # 5. 注册系统 cron 任务
    _bootstrap_cron(ctx)
```

- [ ] **Step 2: 重写 _setup_executor**

```python
def _setup_executor(ctx, factory, args):
    if args.cube_sandbox:
        executor = CubeSandboxExecutor(
            template_id=args.cube_sandbox_template,
            get_llm=lambda agent_id: factory.get_llm(agent_id),
        )
    else:
        executor = InProcessExecutor(
            get_llm=lambda agent_id: factory.get_llm(agent_id),
        )
    ctx.sandbox = ExecutorProvider(executor=executor)
```

- [ ] **Step 3: 删除 _load_residents, _load_workers, _setup_dag_store**

```python
# 删除以下函数：
# - _load_residents
# - _load_workers
# - _setup_dag_store
# - _setup_sub_executor（合并到 load_agents）
# - _seed_default_residents
```

- [ ] **Step 4: 重写 cron bootstrap**

```python
def _bootstrap_cron(ctx):
    """Load cron from config/cron.yaml"""
    import yaml
    cron_path = Path("config/cron.yaml")
    if not cron_path.exists():
        return
    with open(cron_path) as f:
        config = yaml.safe_load(f)
    for task in config.get("tasks", []):
        register_system_task(task["name"], 
            lambda t=task: _execute_cron_task(t, ctx))
```

- [ ] **Step 5: 更新 app.py 的 lifespan**

```python
# cococat/app.py — lifespan 中简化 TaskWorker 和 CronWorker 创建
# TaskWorker 不再需要 pool, dag_store, dag_executor
# CronWorker 不再需要 pool
```

- [ ] **Step 6: Commit**

```bash
git add cococat/core/bootstrap.py cococat/app.py
git commit -m "refactor: simplify bootstrap, remove agent loading, wire Mode system"
```

---

## Phase 6：清理 + 测试修复

### Task 6.1：清理废弃的 config 目录

- [ ] **Step 1: 删除废弃文件**

```bash
rm -rf config/residents/
rm -rf config/prompts/  # 如果存在
```

- [ ] **Step 2: Commit**

```bash
git rm -r config/residents/ config/prompts/
git commit -m "chore: remove deprecated config directories"
```

### Task 6.2：修复所有破坏的测试

- [ ] **Step 1: 运行全部测试找出失败的**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | head -200
```

- [ ] **Step 2: 逐个修复或删除不再适用的测试**

预期需要删除的测试文件：
- `tests/core/test_agent_pool.py` — 已删
- `tests/core/test_dag*.py` — 已删
- `tests/core/test_brain_hands_chain.py` — DAG 相关
- `tests/core/test_task_worker.py` — 依赖 AgentPool
- `tests/core/test_sub_agent.py` — 签名变化
- `tests/core/test_bootstrap.py` — 签名变化
- `tests/core/test_cron_bootstrap.py` — 签名变化
- `tests/core/test_worker.py` — 砍了 _process_dag
- `tests/routes/test_dag_api.py` — 已删

- [ ] **Step 3: 更新 fixture**

```python
# tests/conftest.py — 更新 fixture 不再创建 AgentPool
@pytest.fixture
def app_context():
    from cococat.context import AppContext
    return AppContext()
```

- [ ] **Step 4: 逐步修复和提交**

每个测试文件修复后单独 commit。

---

## 实施依赖图

```
Phase 0 (Mode 配置 + 加载器)
  └─ Phase 1 (砍 AgentPool + 重命名)
       ├─ Phase 2 (ToolCatalog + Prompt 清理)
       ├─ Phase 3 (DB 迁移)
       └─ Phase 5 (Bootstrap + Cron)
            └─ Phase 4 (Routes)
                 └─ Phase 6 (清理 + 测试)
```

Phase 0-3 可一定程度并行。Phase 4 依赖 Phase 1-3 完成。Phase 5 依赖 Phase 1。Phase 6 在所有之后。
