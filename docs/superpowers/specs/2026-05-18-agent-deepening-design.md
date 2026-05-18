# Agent 深化拆分设计

**日期**: 2026-05-18  
**状态**: 设计完成，待审批  
**关联**: 架构深化候选 #1

## 问题

`cococat/core/agent.py` 是一个 323 行的上帝类，混合了 4 种不相关的责任：

| 责任 | 行号 | 描述 |
|------|------|------|
| 构建/配置 | 45-91 | `__init__` 加载 memory、profile、skills，构建 system_prompt，组装 tools |
| 场景绑定 | 93-152 | `bind_to_scene` / `unbind` / `get_tools` — **死代码**，生产路径从未调用 |
| ReAct 执行 | 154-274 | `run()` — 上下文装配、历史加载、ReAct 循环（流式/非流式）、会话持久化、Dream 触发 |
| 工具函数 | 280-323 | `_default_tools` / `_session_path` |

此外，Agent 类还有 8 个 cococat 直接依赖（sandbox_path, prompt, skills, profile, session, tools, tool_executor, providers），传递性依赖贯穿整个 KB/Ingest 管线。

## 事实确认

通过追踪所有生产代码路径，确认：

- `bind_to_scene` / `unbind` 仅在测试中被调用，生产代码中调用次数为 **0**
- `AgentState.IDLE` / `AgentState.WORKING` 同样死代码——实际 busy 追踪在 `SubAgentExecutor._busy` 集合中
- Agent 的实际生命周期：启动时创建 → 加入 Pool → `agent.run(task)` 运行 → 销毁（或沙箱一次性创建）
- 没有「一个 agent 在不同场景间反复 bind/unbind」的实际流程

## 方案

### 模块拆分

```
cococat/core/
├── agent.py              ← 重构 (~150行，原323行)
│   ├── AgentConfig        frozen dataclass ~15行
│   ├── load_agent_config()  工厂函数 ~40行
│   ├── run_agent()          纯执行函数 ~80行
│   └── Agent                薄兼容壳 ~15行
```

### 新接口

```python
@dataclass(frozen=True)
class AgentConfig:
    """Agent 的不可变配置——所有构建在创建时一次性完成。"""
    id: str
    name: str
    role: str            # "resident" | "worker"
    system_prompt: str
    tools: list
    agent_dir: str


def load_agent_config(
    agent_dir: str,
    *,
    scene_config = None,
    tools: list | None = None,
) -> AgentConfig:
    """加载并合并 profile / memory / skills / scene → 不可变 AgentConfig。

    内部调用：
    - load_agent_system_prompt(agent_dir)  → profile_text
    - load_memory_from_agent_dir(agent_dir)  → memory_content, pinned
    - resolve_skills(skill_names)  → skill objects
    - skills_to_prompt(skills)  → prompt fragment
    - skills_to_tools(skills)  → tool list
    - build_system_prompt(...)  → final prompt
    """


async def run_agent(
    config: AgentConfig,
    llm: Any,
    message: str,
    *,
    session: Session | None = None,
    on_text: Callable[[str], Any] | None = None,
    on_tool: Callable[[str, str, dict], Any] | None = None,
    on_reasoning: Callable[[str], Any] | None = None,
    max_iterations: int = 30,
) -> str:
    """执行完整 ReAct 循环：加载历史 → 迭代 LLM → 执行工具 → 持久化会话 → 触发 Dream。"""
```

### 消除的内容

| 删除项 | 所在文件 | 原因 |
|--------|----------|------|
| `Agent.bind_to_scene()` (~40行) | agent.py | 死代码 |
| `Agent.unbind()` (~8行) | agent.py | 死代码 |
| `Agent.get_tools()` (~6行) | agent.py | 工具在 AgentConfig 创建时固定 |
| `Agent.set_scene_tools()` (~3行) | agent.py | 同上 |
| `AgentState` enum (~3行) | agent.py | 死代码 |
| `self.state` / `bound_scene` / `_scene_tools` / `_sandbox` / `_default_system_prompt` | agent.py | 死代码 |
| `AgentPool.bind_to_scene()` (~9行) | agent_pool.py | 委托给 agent 的 bind，死代码 |
| `AgentPool.unbind()` (~5行) | agent_pool.py | 同上 |
| `AgentPool.get_scene_agent()` (~5行) | agent_pool.py | 死代码 |
| `Agent._default_tools()` (~34行) | agent.py | 仅测试使用，移入 test fixtures |
| `Agent._session_path()` (~7行) | agent.py | 合并到 run_agent 内部 |

**总计消除: ~120 行死代码 + ~50 行冗余**

### 受影响的文件

| 文件 | 改动 |
|------|------|
| `cococat/core/agent.py` | 重写：AgentConfig + load_agent_config + run_agent + Agent 壳 |
| `cococat/core/agent_pool.py` | 删除 bind_to_scene / unbind / get_scene_agent |
| `cococat/core/bootstrap.py` | `Agent(...)` → `config = load_agent_config(...)`；Agent 只做薄壳包装 |
| `cococat/core/sandbox/__init__.py` | 同上 |
| `cococat/core/sub_agent.py` | `agent.run(task)` → `run_agent(config, agent._llm, task)` |
| `cococat/core/cron_worker.py` | 同上 |
| `cococat/routes/channels.py` | 同上 |
| `cococat/worker.py` | 删 `agent._llm` 私有访问，改用公开接口 |
| `tests/cococat/test_agent.py` | 更新 bind/unbind 测试为 AgentConfig + run_agent 测试 |
| `tests/cococat/test_agent_pool.py` | 删除 bind/unbind 相关测试 |
| `tests/cococat/test_scene_permissions.py` | 同上 |
| `tests/cococat/test_agent_roles.py` | 同上 |
| `tests/cococat/test_sub_agent.py` | 同上 |
| `tests/cococat/test_integration.py` | 同上 |

### 测试改进

重构前后的测试差异：

```python
# 之前：构造完整 Agent，需 agent_dir + profile + memory + skills
agent = Agent(id="test", name="test", role=AgentRole.WORKER,
              llm=mock_llm, agent_dir="/tmp/test_agent")
result = await agent.run("hello")

# 之后：只需 AgentConfig + mock LLM
config = AgentConfig(
    id="test", name="test", role="worker",
    system_prompt="You are a helpful assistant.",
    tools=[...],
    agent_dir="/tmp/test_agent",
)
result = await run_agent(config, mock_llm, "hello")
```

- `run_agent` 可单独测试，不需要构造完整 Agent 环境
- ReAct 循环逻辑与配置构建完全解耦
- 可注入 mock LLM 测试循环边界（max_iterations、tool_call 处理、error 路径）

### 不改变的行为

- `run_agent` 函数体内部逻辑（ReAct 循环、会话持久化、Dream 触发）与当前 `agent.run()` **逐行等价**
- `Agent` 类保留为薄兼容壳：

```python
class Agent:
    def __init__(self, config: AgentConfig, llm: Any):
        self.config = config
        self.id = config.id
        self.name = config.name
        self.role = config.role
        self.page = ""
        self._llm = llm

    async def run(self, message: str, **kwargs) -> str:
        return await run_agent(self.config, self._llm, message, **kwargs)
```

现有 `agent.run(message, ...)` 调用行为不变
- `AgentPool.get_free_workers()` 中去掉 `a.state == AgentState.IDLE` 检查——因为 state 始终是 IDLE（bind/unbind 从未调用），这个检查是空操作。busy 追踪实际在 `SubAgentExecutor._busy` 中

## 实施顺序

1. 创建 `AgentConfig` dataclass + `load_agent_config()` 工厂函数
2. 创建 `run_agent()` 纯函数（从 `agent.run()` 提取逻辑）
3. 重构 `Agent` 类为薄壳（委托给 AgentConfig + run_agent）
4. 更新 `bootstrap.py` 和 `sandbox/__init__.py` 使用 `load_agent_config()`
5. 更新所有 `agent.run()` 调用方
6. 删除死代码（bind_to_scene / unbind / AgentState）
7. 更新测试
8. 运行全量测试确认零回退
