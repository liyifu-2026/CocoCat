# CocoCat 架构重构记录

## 概览

2026-05-17 对核心代码库进行了 7 项架构深化，目标是提高局部性和可测试性。

## 变更清单

### 1. Database 拆分 (`cococat/db/`)

**前**: `database.py` 424 行单体类包含 8 个实体的 SQL 查询和迁移。  
**后**: 拆分为 8 个 Store，每个只管自己的表。

| Store | 文件 | 职责 |
|-------|------|------|
| `AgentStore` | `agent_store.py` | agents 表 CRUD |
| `TaskStore` | `task_store.py` | tasks 表 CRUD |
| `SceneStore` | `scene_store.py` | scenes 表 CRUD |
| `MessageStore` | `message_store.py` | messages 表写入/查询 |
| `FactStore` | `fact_store.py` | facts 表 + FTS5 索引 |
| `TodoStore` | `todo_store.py` | todos 表保存/加载 |
| `DagRunStore` | `dag_run_store.py` | dag_runs 表 |
| `Database` | `database.py` | 仅连接/迁移/底层查询 |

调用方式: `ctx.db.list_agents()` → `ctx.db.agents.list_all()`

### 2. 频道抽象合并 (`cococat/core/channels/`)

**前**: `channel_adapter.py` (ChannelAdapter ABC) 和 `core/channels/base.py` (ChannelBase) 两套平行抽象。  
**后**: 删除 `channel_adapter.py`，合并到 `core/channels/`。

- `Channel` Protocol 移入 `base.py`
- 富媒体 helpers (`text_reply`, `chunk_text` 等) 移入 `ChannelBase`
- 类型系统统一到 `context.py`

### 3. ToolContext 瘦身 (`cococat/core/types.py`)

**前**: 15+ 键的 TypedDict，每个工具用 `ctx.get("xxx")` 挖掘自己需要的值。  
**后**: 分组为 4 个 provider:

```
ToolContext
├── dag:     DagEnv      (store, executor, dag_dir, ...)
├── sandbox: SandboxEnv   (run)
├── memory:  MemoryEnv    (memory_path, agent_dir, exp_path)
├── web:     WebEnv       (tavily_api_key)
└── agent_id, agent_dir, role, session_id, db
```

测试 web_search: `ToolContext(web=WebEnv(tavily_api_key="fake"))` — 无需构造 dag/memory 等不相关部分。

### 4. 记忆系统合并 (`cococat/memory/store.py`)

**前**: 三套机制各管一摊
- `tools/memory_tools.py` — pin/recall 手动
- `core/dream.py` — auto-dream 对话提取
- `memory/ticker.py` + `compiler.py` + `facts.py` — 定期编译 + FTS5 提取

**后**: 统一为 `MemoryStore` 单一模块，暴露统一接口:
- `remember(text)` / `recall(query)` / `forget(keyword)` — 手动操作
- `dream(session_path)` — 自动对话提取
- `compile()` — 每日编译 today → week → longterm
- `extract_facts()` — 原子事实写入 FTS5

### 5. Prompt 工具列表动态生成 (`cococat/prompt.py`)

**前**: `STATIC_PREFIX` 字符串硬编码所有工具名称和描述。  
**后**: `build_tool_section(tools)` 从实际 Tool 对象生成工具清单。加新工具自动反映到 prompt。

### 6. Bootstrap 拆分 (`cococat/core/bootstrap.py`)

**前**: `load_agents()` ~120 行函数串行创建所有服务。  
**后**: 拆为 5 个独立工厂函数:
- `_setup_providers()` — 凭证 + LLM 工厂
- `_setup_dag_store()` — DAG 存储
- `_setup_sandbox()` — 沙箱提供者
- `_setup_sub_executor()` — 子代理调度器
- `_load_residents()` / `_load_workers()` — 加载代理

`load_agents()` 变为纯编排调用。

### 7. 认证 + 清理

- 新增 `cococat/auth.py` — JWT Bearer + X-API-Key 中间件
- 删除死代码: `web/main.py`, `py-agent/`
- 提取 `routes/chat.py` 中 WebSocket 流回调为 `_make_event_handler()` / `_make_stream_callbacks()`

## 测试

全部 160 个测试通过，lint 零新增。
