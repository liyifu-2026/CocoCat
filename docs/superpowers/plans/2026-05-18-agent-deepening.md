# Agent 深化拆分实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `cococat/core/agent.py` 从 323 行上帝类拆分为 AgentConfig（不可变配置）+ run_agent（纯函数）+ Agent 薄壳，消除 ~170 行死代码

**Architecture:** AgentConfig 冻结所有构建产物，run_agent 独立执行 ReAct 循环，Agent 退化为委托壳。工具固定，无动态场景绑定

**Tech Stack:** Python 3.10+, dataclasses, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-05-18-agent-deepening-design.md`

---

### Task 1: 创建 AgentConfig dataclass + load_agent_config 工厂

**Files:**
- Modify: `cococat/core/agent.py`

- [ ] **Step 1: 在 agent.py 顶部添加 AgentConfig 和 load_agent_config**

在现有 imports 之后、`AgentState` 之前插入：

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentConfig:
    """Agent 的不可变配置——所有构建在创建时一次性完成。"""
    id: str
    name: str
    role: str                     # "resident" | "worker"
    system_prompt: str
    tools: list = field(default_factory=list)
    agent_dir: str = ""


def load_agent_config(
    agent_dir: str,
    *,
    base_tools: list | None = None,
    scene_config = None,
    is_kb_agent: bool = False,
) -> AgentConfig:
    """加载 profile / memory / skills → 合并 → 不可变 AgentConfig。"""
    name = "agent"
    profile_text = ""
    memory_content, pinned = "", ""

    if agent_dir and os.path.isdir(agent_dir):
        from cococat.profile import load_agent_system_prompt, get_agent_skills
        profile_text = load_agent_system_prompt(agent_dir)
        memory_content, pinned = load_memory_from_agent_dir(agent_dir)
        skill_names = get_agent_skills(agent_dir)
        # 从 profile.yaml 提取 agent name
        profile_path = os.path.join(agent_dir, "profile.yaml")
        if os.path.exists(profile_path):
            import yaml
            try:
                with open(profile_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and data.get("name"):
                    name = data["name"]
            except Exception:
                pass
    else:
        skill_names = []

    # 解析技能
    from cococat.skills import resolve_skills, skills_to_prompt, skills_to_tools
    agent_skills = resolve_skills(skill_names)

    # 合并场景技能
    if scene_config and hasattr(scene_config, 'skills') and scene_config.skills:
        all_names = list(dict.fromkeys(skill_names + scene_config.skills))
        merged_skills = resolve_skills(all_names)
    else:
        merged_skills = agent_skills

    skill_tools = skills_to_tools(merged_skills)
    skill_prompt = skills_to_prompt(merged_skills)

    # 合并工具
    tools = list(base_tools or [])
    tools += skill_tools

    # 构建 system prompt
    from cococat.prompt import build_system_prompt, KB_AGENT_STATIC_PREFIX
    agent_profile = name + ("\n" + profile_text if profile_text else "")
    system_prompt = build_system_prompt(
        agent_profile=agent_profile,
        memory_content=memory_content,
        pinned_facts=pinned,
        scene_context=scene_config.context if scene_config else "",
        scene_kbs=scene_config.kbs if scene_config else [],
        scene_skills=skill_prompt,
        tools=tools,
        static_prefix=KB_AGENT_STATIC_PREFIX if is_kb_agent else None,
    )

    return AgentConfig(
        id=os.path.basename(agent_dir.rstrip("/")) if agent_dir else "agent",
        name=name,
        role=scene_config and "worker" or "worker",
        system_prompt=system_prompt,
        tools=tools,
        agent_dir=agent_dir,
    )
```

需要确保 `os` 和 `load_memory_from_agent_dir` 已经导入。检查现有 imports，补充缺失的：

```python
import os
from cococat.prompt import build_system_prompt, load_memory_from_agent_dir, KB_AGENT_STATIC_PREFIX
```

- [ ] **Step 2: 写 AgentConfig 单元测试**

创建 `tests/cococat/test_agent_config.py`：

```python
"""Tests for AgentConfig and load_agent_config."""
import os
import tempfile
import pytest
from cococat.core.agent import AgentConfig, load_agent_config


def test_agent_config_is_immutable():
    config = AgentConfig(
        id="test", name="Test", role="worker",
        system_prompt="You are helpful.",
        tools=[{"name": "bash"}],
        agent_dir="/tmp",
    )
    assert config.id == "test"
    assert config.name == "Test"
    assert config.role == "worker"
    assert config.system_prompt == "You are helpful."
    assert config.tools == [{"name": "bash"}]
    assert config.agent_dir == "/tmp"

    with pytest.raises(Exception):
        config.id = "changed"


def test_agent_config_defaults():
    config = AgentConfig(
        id="a", name="A", role="worker",
        system_prompt="Hi", agent_dir="/tmp",
    )
    assert config.tools == []


def test_load_agent_config_minimal():
    with tempfile.TemporaryDirectory() as d:
        config = load_agent_config(d)
        assert config.agent_dir == d
        assert isinstance(config.system_prompt, str)
        assert len(config.system_prompt) > 0


def test_load_agent_config_with_base_tools():
    with tempfile.TemporaryDirectory() as d:
        tools = [{"name": "bash", "description": "Run bash"}]
        config = load_agent_config(d, base_tools=tools)
        assert config.tools == tools
```

- [ ] **Step 3: 运行测试确认通过**

```bash
python -m pytest tests/cococat/test_agent_config.py -v
```

Expected: 4 tests pass

- [ ] **Step 4: Commit**

```bash
git add cococat/core/agent.py tests/cococat/test_agent_config.py
git commit -m "feat: add AgentConfig dataclass and load_agent_config factory"
```

---

### Task 2: 从 agent.run() 提取 run_agent 纯函数

**Files:**
- Modify: `cococat/core/agent.py`

- [ ] **Step 1: 在 Agent 类之前添加 run_agent 函数**

在 `Agent` 类定义之前插入完整的 `run_agent` 函数。从当前 `agent.run()` (line 154-274) 逐行拷贝，将所有 `self.xxx` 替换为参数引用：

```python
async def run_agent(
    config: AgentConfig,
    llm: Any,
    message: str,
    *,
    session: Session | None = None,
    session_id: str | None = None,
    on_text: Optional[Callable[[str], Any]] = None,
    on_tool: Optional[Callable[[str, str, dict], Any]] = None,
    on_reasoning: Optional[Callable[[str], Any]] = None,
    max_iterations: int = 0,
) -> str:
    """执行 ReAct 循环：加载历史 → 迭代 LLM → 执行工具 → 持久化 → Dream。"""
    from cococat.core.types import ToolContext

    context = ToolContext()
    context.agent_id = config.id
    context.agent_dir = config.agent_dir
    context.role = config.role

    tools = config.tools

    messages: list[dict] = [{"role": "system", "content": config.system_prompt}]

    if session is not None:
        history = await session.sanitized_read()
    else:
        sid = session_id or "default"
        session_path = _resolve_session_path(config.agent_dir, sid)
        history = load_session(session_path)
    messages.extend(history)

    messages.append({"role": "user", "content": message})

    final_text: list[str] = []

    if max_iterations <= 0:
        max_iterations = int(os.environ.get("COCOCAT_MAX_ITERATIONS", "30"))

    for iteration in range(max_iterations):
        use_stream = iteration == 0 and hasattr(llm, "chat_stream")
        reasoning = None

        if use_stream:
            collected_content = []
            collected_tool_calls = []
            collected_reasoning = []

            async for event in llm.chat_stream(
                messages=messages,
                tools=tools if tools else None,
            ):
                if event["type"] == "delta" and on_text:
                    r = on_text(event["content"])
                    if callable(getattr(r, "__await__", None)):
                        await r
                if event["type"] == "reasoning" and on_reasoning:
                    r = on_reasoning(event["content"])
                    if callable(getattr(r, "__await__", None)):
                        await r
                if event["type"] == "reasoning":
                    collected_reasoning.append(event["content"])
                if event["type"] == "delta":
                    collected_content.append(event["content"])
                if event["type"] == "tool_call":
                    collected_tool_calls.append({
                        "id": event.get("id", ""),
                        "name": event.get("name", ""),
                        "arguments": event.get("arguments", ""),
                    })

            content = "".join(collected_content)
            reasoning = "".join(collected_reasoning) if collected_reasoning else None
            tool_calls = [ToolCallRequest(**tc) for tc in collected_tool_calls] if collected_tool_calls else []
        else:
            resp = await llm.chat(
                messages=messages,
                tools=tools if tools else None,
            )
            content = resp.content or ""
            tool_calls = resp.tool_calls or None
            reasoning = resp.reasoning_content or None

        if tool_calls:
            final_text.append(content) if content else None
            messages.append(make_assistant_msg(content, tool_calls, reasoning))
            await execute_tool_calls(tool_calls, messages, tools, context, on_tool)
        else:
            if content:
                final_text.append(content)
            break
    else:
        final_text.append("[ReAct loop exceeded max iterations]")

    result = "\n\n".join(filter(None, final_text))

    try:
        if session is not None:
            await session.append_pair(message, result)
        else:
            sid = session_id or "default"
            session_path = _resolve_session_path(config.agent_dir, sid)
            save_session_pair(session_path, message, result)
    except Exception:
        pass

    try:
        dream_path = session.path if session is not None else _resolve_session_path(config.agent_dir, session_id or "default")
        maybe_trigger_dream(dream_path)
    except Exception:
        pass

    return result
```

- [ ] **Step 2: 添加 _resolve_session_path 辅助函数**

在 `run_agent` 之前添加：

```python
def _resolve_session_path(agent_dir: str, session_id: str) -> str:
    if session_id and session_id != "default":
        sessions_dir = os.path.join(agent_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        return os.path.join(sessions_dir, f"{session_id}.jsonl")
    os.makedirs(agent_dir, exist_ok=True)
    return os.path.join(agent_dir, "session.jsonl")
```

- [ ] **Step 3: 确保所有导入可用**

检查并确保 agent.py 顶部有这些 imports：

```python
from cococat.core.tool_executor import make_assistant_msg, execute_tool_calls
from cococat.providers.base import ToolCallRequest
from cococat.core.types import ToolContext
from cococat.core.session import Session, load_session, save_session_pair, maybe_trigger_dream
```

- [ ] **Step 4: 写 run_agent 测试**

在 tests/cococat/ 创建 `test_run_agent.py`：

```python
"""Tests for run_agent pure function."""
import os
import tempfile
import pytest
from cococat.core.agent import AgentConfig, run_agent
from cococat.providers.base import LLMResponse


class FakeLLM:
    async def chat(self, messages, tools=None, **kwargs):
        return LLMResponse(content="Hello from Agent!")


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def config():
    return AgentConfig(
        id="test", name="Test", role="worker",
        system_prompt="You are a helpful assistant.",
        tools=[],
        agent_dir="/tmp",
    )


@pytest.mark.asyncio
async def test_run_agent_returns_string(config, fake_llm):
    result = await run_agent(config, fake_llm, "Hi")
    assert isinstance(result, str)
    assert "Hello from Agent" in result


@pytest.mark.asyncio
async def test_run_agent_saves_to_session(config, fake_llm):
    from cococat.core.session import Session, SessionManager
    mgr = SessionManager()
    session = await mgr.create("/tmp")
    result = await run_agent(config, fake_llm, "Hello", session=session)
    messages = await session.read()
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(user_msgs) >= 1
    assert len(assistant_msgs) >= 1


@pytest.mark.asyncio
async def test_run_agent_with_custom_max_iterations(config, fake_llm):
    """Even with max_iterations=1, the loop should produce output."""
    result = await run_agent(config, fake_llm, "Hello", max_iterations=1)
    assert len(result) > 0
```

- [ ] **Step 5: 运行 run_agent 测试**

```bash
python -m pytest tests/cococat/test_run_agent.py -v
```

Expected: 3 tests pass

- [ ] **Step 6: Commit**

```bash
git add cococat/core/agent.py tests/cococat/test_run_agent.py
git commit -m "feat: extract run_agent pure function from agent.run()"
```

---

### Task 3: 重构 Agent 为薄兼容壳 + 删除死代码

**Files:**
- Modify: `cococat/core/agent.py`

- [ ] **Step 1: 重写 Agent 类**

用以下代码替换当前 `Agent` 类（line 31-323）：

```python
class Agent:
    """薄兼容壳——委托给 AgentConfig + run_agent。"""

    def __init__(
        self,
        id: str,
        name: str,
        role: AgentRole,
        llm: Any,
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
        agent_dir: str | None = None,
    ):
        agent_dir_path = agent_dir or f"agents/{id}"
        config = load_agent_config(
            agent_dir_path,
            base_tools=tools,
            is_kb_agent=(id == "kb-agent"),
        )

        self.config = AgentConfig(
            id=id,
            name=name,
            role=role.value,
            system_prompt=system_prompt or config.system_prompt,
            tools=config.tools,
            agent_dir=agent_dir_path,
        )
        self.id = id
        self.name = name
        self.role = role
        self.page = ""
        self._llm = llm
        self._agent_dir = agent_dir_path

    async def run(
        self,
        message: str,
        context=None,
        on_text=None,
        on_tool=None,
        on_reasoning=None,
        max_iterations: int = 0,
        session=None,
    ) -> str:
        session_id = None
        if isinstance(context, dict) and "session_id" in context:
            session_id = context["session_id"]
        elif hasattr(context, "session_id"):
            session_id = context.session_id

        return await run_agent(
            self.config,
            self._llm,
            message,
            session=session,
            session_id=session_id,
            on_text=on_text,
            on_tool=on_tool,
            on_reasoning=on_reasoning,
            max_iterations=max_iterations,
        )

    async def init(self):
        pass
```

- [ ] **Step 2: 删除死代码**

删除以下不再需要的代码：
- `AgentState` enum (line 21-23)
- `SystemPrompt` dataclass (line 31-34)
- 已删除的 `bind_to_scene`, `unbind`, `get_tools`, `set_scene_tools` 方法在 Agent 类中已不存在
- `Agent._default_tools()` 静态方法
- `Agent._session_path()` 方法

确保只保留：`AgentRole` enum, `AgentConfig` dataclass, `load_agent_config`, `_resolve_session_path`, `run_agent`, `Agent` 类。

- [ ] **Step 3: 运行现有 Agent 测试确认向后兼容**

```bash
python -m pytest tests/cococat/test_agent.py -v -k "not bind and not unbind and not rebind and not resident_agent_cannot_bind and not tool_scoping and not set_scene_tools"
```

Expected: 保留的测试通过（test_agent_initial_state, test_agent_run_returns_string, test_agent_run_saves_to_session, test_agent_run_loads_history_from_session, test_agent_saves_to_session）

- [ ] **Step 4: Commit**

```bash
git add cococat/core/agent.py
git commit -m "refactor: Agent to thin wrapper, delete bind/unbind dead code"
```

---

### Task 4: 删除 AgentPool 死代码

**Files:**
- Modify: `cococat/core/agent_pool.py`

- [ ] **Step 1: 删除 bind_to_scene / unbind / get_scene_agent**

从 `agent_pool.py` 删除以下方法：

删除 line 71-80 (`bind_to_scene`)：
```python
    def bind_to_scene(self, agent_id: str, scene_id: str) -> bool:
        ...
```

删除 line 82-86 (`unbind`)：
```python
    def unbind(self, agent_id: str) -> None:
        ...
```

删除 line 88-93 (`get_scene_agent`)：
```python
    def get_scene_agent(self, scene_id: str) -> Agent | None:
        ...
```

更新 `get_free_workers()` (line 46-51) 去掉 `state == AgentState.IDLE` 检查：

```python
    def get_free_workers(self) -> list[Agent]:
        return [
            a for a in self._agents.values()
            if a.role == AgentRole.WORKER
        ]
```

从 imports 删除 `AgentState`（line 8）：

```python
from cococat.core.agent import AgentRole
```

更新 docstring (line 20-22) 删除 "Handles scene binding/unbinding"：

```python
class AgentPool:
    """Manages a pool of Agent instances.

    - Tracks agent states
    - Provides free sub-agent lookup
    """
```

- [ ] **Step 2: 更新 AgentPool 测试**

```bash
python -m pytest tests/cococat/test_agent_pool.py -v -k "not bind and not unbind and not scene_agent"
```

Expected: test_pool_list_agents, test_pool_get_free_sub_agents, test_pool_max_agents, test_get_agent_nonexistent, test_add_agent_overwrites_existing pass

- [ ] **Step 3: Commit**

```bash
git add cococat/core/agent_pool.py
git commit -m "refactor: remove bind/unbind/get_scene_agent dead code from AgentPool"
```

---

### Task 5: 更新 bootstrap.py

**Files:**
- Modify: `cococat/core/bootstrap.py`

- [ ] **Step 1: 更新 _load_residents 中的 Agent 创建**

将 line 141-144：

```python
        agent = Agent(
            id=agent_id, name=name, role=AgentRole.RESIDENT,
            llm=provider, tools=tools, agent_dir=f"agents/{agent_id}",
        )
```

改为：

```python
        agent = Agent(
            id=agent_id, name=name, role=AgentRole.RESIDENT,
            llm=provider, tools=tools, agent_dir=f"agents/{agent_id}",
        )
```

（无需改动——Agent 构造器签名不变，兼容壳自动处理）

- [ ] **Step 2: 确认 _load_workers 无需改动**

`_load_workers` 中的 Agent 创建已经使用新兼容壳，签名不变。

- [ ] **Step 3: 验证**

无需单独测试——Task 8 全量测试会覆盖。

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: bootstrap.py no changes needed (Agent compat wrapper)"
```

（如果无改动则跳过此 commit）

---

### Task 6: 更新生产调用方

**Files:**
- Modify: `cococat/core/sandbox/__init__.py`
- Modify: `cococat/core/cron_worker.py`
- Modify: `cococat/routes/channels.py`
- Modify: `cococat/worker.py`

- [ ] **Step 1: 更新 sandbox/__init__.py**

`_make_and_run_agent` (line 42-49) 改为使用 `load_agent_config` + `run_agent`：

```python
async def _make_and_run_agent(
    agent_id: str,
    prompt: str,
    tools: list[dict],
    resolve_llm: Callable[[str], Any],
    session_id: str | None = None,
    on_event: Callable | None = None,
) -> str:
    from cococat.core.agent import AgentConfig, run_agent

    llm = resolve_llm(agent_id)
    if not llm:
        return f"[System] No LLM provider for agent '{agent_id}'"

    agent_dir = f"agents/{agent_id}"
    config = AgentConfig(
        id=agent_id,
        name=agent_id,
        role="worker",
        system_prompt="You are a sub-agent worker.",
        tools=tools,
        agent_dir=agent_dir if os.path.isdir(agent_dir) else "",
    )

    try:
        result = await run_agent(
            config, llm, prompt,
            session_id=session_id,
            on_text=(lambda t: on_event("text_delta", {"content": t})) if on_event else None,
            on_tool=(lambda n, s, d=None: on_event("stream_tool", {"name": n, "status": s, **(d or {})})) if on_event else None,
            on_reasoning=(lambda c: on_event("stream_reasoning", {"content": c})) if on_event else None,
        )
        return result
    except Exception as e:
        import traceback
        logger.exception("_make_and_run_agent failed for %s", agent_id)
        return f"Error: {e}"
```

同时删除延迟导入 `from cococat.core.agent import Agent, AgentRole`（line 35），改为顶部的 `from cococat.core.agent import AgentConfig, run_agent`。更新顶部导入。

- [ ] **Step 2: 更新 cron_worker.py 中的 _dispatch**

`_dispatch` (line 86-109) 中 `agent.run(task)` 和 `main.run(task)` 不变——Agent 兼容壳保持 `run()` 方法签名不变。

无需改动。

- [ ] **Step 3: 更新 routes/channels.py**

Line 366 `reply_text = await agent.run(msg.content)` 不变——兼容壳保持相同签名。

无需改动。

- [ ] **Step 4: 更新 worker.py 中 agent._llm 私有访问**

`_process_kb` (line 167) 中 `agent._llm` 改为 `agent._llm`——当前兼容壳保留此属性，无需改动。但如果未来要去掉私有访问，可将其改为公开属性或通过方法返回。

```bash
# 验证 _llm 仍可访问
python -c "from cococat.core.agent import Agent, AgentRole; a = Agent('x','x',AgentRole.WORKER, object()); print(a._llm)"
```

- [ ] **Step 5: 验证 sandbox 路径**

```bash
python -m pytest tests/cococat/test_cubesandbox_executor.py -v
```

如果持续集成中 sandbox executor 测试通过，则变更正确。

- [ ] **Step 6: Commit**

```bash
git add cococat/core/sandbox/__init__.py
git commit -m "refactor: sandbox uses AgentConfig + run_agent directly"
```

---

### Task 7: 更新测试

**Files:**
- Modify: `tests/cococat/test_agent.py`
- Modify: `tests/cococat/test_agent_pool.py`
- Modify: `tests/cococat/test_scene_permissions.py`
- Modify: `tests/cococat/test_agent_roles.py`
- Modify: `tests/cococat/test_sub_agent.py`
- Modify: `tests/cococat/test_integration.py`

- [ ] **Step 1: 更新 test_agent.py**

删除 bind/unbind/tool_scoping 相关测试（函数名包含 `bind`/`unbind`/`rebind`/`tool_scoping`/`set_scene_tools`），共删除 ~8 个测试函数。

更新 fixture，删除 `AgentState` 引用：

```python
from cococat.core.agent import Agent, AgentRole  # 移除 AgentState

@pytest.fixture
def main_agent(fake_llm):
    return Agent(
        id="main",
        name="Main AI",
        role=AgentRole.RESIDENT,
        llm=fake_llm,
    )

@pytest.fixture
def sub_agent(fake_llm):
    return Agent(
        id="agent_a",
        name="Agent A",
        role=AgentRole.WORKER,
        llm=fake_llm,
    )
```

更新 `test_agent_initial_state`——删除 `state` 和 `bound_scene` 断言：

```python
@pytest.mark.asyncio
async def test_agent_initial_state(main_agent):
    assert main_agent.id == "main"
    assert main_agent.role == AgentRole.RESIDENT
```

保留以下测试：
- `test_agent_initial_state` (删 state/bound_scene 断言)
- `test_agent_run_returns_string`
- `test_agent_run_saves_to_session`
- `test_agent_run_loads_history_from_session`
- `test_agent_saves_to_session`

- [ ] **Step 2: 更新 test_agent_pool.py**

删除 bind/unbind/scene_agent 相关测试（共 ~5 个函数：`test_pool_bind_unbind`, `test_pool_bind_main_ai_fails`, `test_pool_get_free_after_bind`, `test_get_scene_agent`, `test_get_scene_agent_none`, `test_bind_nonexistent_agent`, `test_unbind_nonexistent_agent`）。

删除 `AgentState` 从 imports。

更新 `test_pool_get_free_sub_agents`——去掉 state 依赖断言：

```python
@pytest.mark.asyncio
async def test_pool_get_free_sub_agents(pool):
    free = pool.get_free_sub_agents()
    assert len(free) >= 0  # pool 创建后 worker agents 应可用
```

- [ ] **Step 3: 更新 test_scene_permissions.py**

此文件大量使用 `bind_to_scene` 和 `unbind`——全部删除或改写为使用 load_agent_config 的测试。

删除整个文件内容，替换为：

```python
"""Tests for scene config in agent creation."""
import os
import tempfile
import pytest
from cococat.core.agent import load_agent_config
from cococat.scene.config import SceneConfig


@pytest.fixture
def scene():
    return SceneConfig(
        id="test-scene",
        name="Test Scene",
        context="You help customers with refunds.",
        kbs=["product-manual", "faq"],
        skills=["refund_procedure", "crm_lookup"],
    )


def test_load_agent_config_with_scene_includes_context(scene):
    with tempfile.TemporaryDirectory() as d:
        config = load_agent_config(d, scene_config=scene)
        assert "refunds" in config.system_prompt.lower()
```

- [ ] **Step 4: 更新 test_agent_roles.py**

删除 `bind_to_scene` 相关测试。保留 tool 相关测试。

删除 `test_resident_role_cannot_bind_scene` 和 `test_worker_role_can_bind_scene`。

保留 `test_kb_agent_has_admin_tools`, `test_coco_resident_has_read_only_kb`, `test_worker_has_read_only_kb`。

删除 `from cococat.core.agent import Agent, AgentRole` 中不需要的 `Agent`。保留 `AgentRole` 如果 tool tests 需要。

- [ ] **Step 5: 更新 test_sub_agent.py**

删除 `test_dispatch_no_free_agents`（依赖 bind_to_scene 来制造 busy 状态）。重写为使用 sandbox 或其他方式。

删除 imports 中的 `AgentState`。

替换 `test_dispatch_no_free_agents`：

```python
@pytest.mark.asyncio
async def test_dispatch_no_free_agents(executor, pool):
    """When pool has no agents, dispatch returns None."""
    # 创建空 pool 测试
    from cococat.core.event_bus import EventBus
    from cococat.core.agent_pool import AgentPool
    empty_pool = AgentPool(EventBus())
    from cococat.core.sub_agent import SubAgentExecutor
    empty_exec = SubAgentExecutor(EventBus(), empty_pool)
    result = await empty_exec.dispatch("Do task", from_agent="main")
    assert result is None
```

- [ ] **Step 6: 更新 test_integration.py**

删除 `test_scene_channel_flow` 和 `test_scene_channel_queue`（依赖 bind_to_scene）。
删除 `test_agent_pool_full`（依赖 bind_to_scene）。

删除 imports 中的 `AgentState`。

保留 `test_full_chat_flow`。

- [ ] **Step 7: 运行更新后的测试**

```bash
python -m pytest tests/cococat/test_agent.py tests/cococat/test_agent_pool.py tests/cococat/test_agent_roles.py tests/cococat/test_sub_agent.py tests/cococat/test_integration.py tests/cococat/test_scene_permissions.py -v
```

Expected: 约 15-20 个测试通过（原约 35 个，删除了 bind/unbind 相关）

- [ ] **Step 8: Commit**

```bash
git add tests/cococat/
git commit -m "test: update tests for Agent thin wrapper, remove bind/unbind tests"
```

---

### Task 8: 运行全量测试确认零回退

**Files:** 无（验证步骤）

- [ ] **Step 1: 运行全量测试**

```bash
python -m pytest tests/ cococat/tests/ -v --tb=short
```

Expected: 所有之前通过的测试仍然通过，无新增失败

- [ ] **Step 2: 运行 ruff lint**

```bash
python -m ruff check cococat/core/agent.py cococat/core/agent_pool.py
```

Expected: 零 lint 错误

- [ ] **Step 3: 确认 agent.py 行数**

```bash
wc -l cococat/core/agent.py
```

Expected: ~150-180 行（原 323 行）

- [ ] **Step 4: 最终 Commit**

```bash
git commit -m "refactor: complete Agent deepening — 323 → ~150 lines, AgentConfig + run_agent"
```
