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

### 8. 配置集中化 + 工具装配 + DI 修复 (2026-05-19)

#### 8a. 删除死代码

- 删除 `web/` 目录（空包，零引用）
- 删除 `cococat/core/dream.py`（17 行透传，内联到 `session.py:maybe_trigger_dream`）

#### 8b. ConfigStore 集中化 (`cococat/config_store.py`)

**前**: 配置加载散落在 50+ 处，用不一致的错误处理和缓存策略：
- `tools/__init__.py` 中 `_resolve_tavily_key()` 内联 `json.load("config/auth.json")`
- `bootstrap.py` 中 `_load_worker_default_model()` 独立函数
- `routes/settings.py` 中 `_read_env()` / `_write_env()` 
- `routes/channels.py` 中 `_load_main_config()` / `_save_main_config()`
- `routes/providers.py` 中 `_load_user_models()` / `_load_custom_providers()` 等

**后**: 单一 `ConfigStore` 模块提供类型化接口：
- `get_auth()` / `set_auth()` — auth.json
- `get_env()` / `set_env()` — .env + os.environ  
- `get_default()` / `save_defaults()` — defaults.json
- `get_channel_configs()` / `save_channel_configs()` — main.yaml
- `get_models()` / `save_models()` — models.json
- `get_custom_providers()` / `save_custom_providers()` — providers.json
- `get_coco_prompt()` / `save_coco_prompt()` — prompts/coco.txt
- `get_resident_configs()` / `save_resident_config()` — residents/*.yaml

路径支持环境变量覆盖：`COCOCAT_AUTH_FILE`, `COCOCAT_MODELS_FILE`, `COCOCAT_CUSTOM_PROVIDERS_FILE`, `COCOCAT_ENV_FILE`。

ConfigStore 在 `app.py:create_app()` 初始化并注入 `AppContext.config_store`。路由处理器通过 FastAPI `Depends(get_ctx)` 获取。

#### 8c. ToolCatalog 工具装配 (`cococat/core/tools/__init__.py`)

**前**: 3 个函数 `create_core_tools()`, `create_main_ai_tools()`, `create_resident_tools()` 各自拼接 `make_*()` 函数，调用方分布在 5+ 处。

**后**: `ToolCatalog` 类提供命名预设：
- `catalog.worker()` — Worker 全工具集
- `catalog.main_ai()` — Main AI 编排工具
- `catalog.resident(kb_agent=True/False)` — Resident 工具

旧函数保留为向后兼容别名（委托给 ToolCatalog）。生产调用方（routes、bootstrap、worker、local_executor）已迁移至 ToolCatalog。

#### 8d. DI 修复

**前**: `routes/settings.py` 和 `routes/agents.py` 的部分路由处理器直接调用 `get_ctx_static()` 而非使用 FastAPI `Depends(get_ctx)`。

**后**: 所有路由处理器统一使用 `ctx: AppContext = Depends(get_ctx)` 进行依赖注入。

### 9. ChannelManager 提取 (2026-05-19)

**前**: `routes/channels.py` (562 行) 混杂 HTTP 路由、频道生命周期管理（启动/停止线程）、配置 I/O、消息处理和内联工具构建。模块级字典 `CHANNEL_STATUS` 和 `CHANNEL_INSTANCES` 管理全局状态。

**后**: 提取 `cococat/core/channel_manager.py` 的 `ChannelManager` 类：
- 拥有 `_instances` 和 `_status` 的管理
- 提供 `connect()` / `disconnect()` / `auto_reconnect()` 方法
- 统一了场景频道和主频道两种连线逻辑（`_wire_scene` / `_wire_main`）
- 路由处理器变为薄委托层，仅调用 `ctx.channel_manager.connect(...)` 等

`routes/channels.py` 从 569 行瘦身至约 200 行。频道生命周期逻辑集中在单一模块，支持为测试提供内存 adapter。

### 10. MemoryStore 多继承 → 组合 (2026-05-19)

**前**: `MemoryStore` 通过 5 个 mixin 类多继承 (`_ManualMixin`, `_DreamMixin`, `_SummarizeMixin`, `_CompileMixin`, `_FactsMixin`)，接口分布在 6 个文件中。每个 mixin 隐式依赖 `self._llm`、`self._db`、`self._memory_dir` 等状态，契约不显式。

**后**: 5 个 mixin 转为独立类（`ManualMemory`, `DreamMemory`, `SummarizeMemory`, `CompileMemory`, `FactsMemory`），每个在构造函数中显式声明依赖。`MemoryStore` 改为组合模式：
```python
class MemoryStore:
    def __init__(self, llm=None, db=None, memory_dir="memory"):
        get_llm = self._get_llm
        self._manual = ManualMemory(memory_dir=memory_dir, db=db)
        self._dream = DreamMemory(get_llm=get_llm)
        ...
```

- `_turn_counts` 和 `_fingerprints` 移入 `SummarizeMemory` 自身状态
- `_fact_snapshots` 移入 `FactsMemory` 自身状态
- 每个子系统可独立测试（如 `DreamMemory(get_llm=mock_llm)`）
- 公共 API 不变（委托模式保持向后兼容）

## 测试

全部 246 个测试通过（1 个预制 `test_dag_api.py:test_list_dag_runs_with_data` 失败除外）。
