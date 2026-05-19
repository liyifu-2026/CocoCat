# Phase 2: 测试覆盖 + 迁移治理

> 接续 Phase 1 的 6 项架构深化。Phase 1 地址：`docs/architecture-refactor-2026-05-17.md`

## 目标

从 7.5/10 → 9/10。两条线并行：

- **测试线**：核心模块回归覆盖
- **治理线**：SQL 迁移版本化 + ADR 记录

---

## Line A: 测试覆盖

### 原则

- 每个模块的测试文件对应 `{module}_test.py`，放在 `cococat/tests/` 下
- 测试的 seam = 模块的 interface（不测内部实现细节）
- 用临时目录 + mock 对象，不依赖运行中的应用

### 阶段 1: 安全 + 配置（3 个文件，最高 ROI）

| 模块 | 文件 | 测试重点 | 行数估算 |
|------|------|----------|---------|
| ConfigStore | `cococat/tests/test_config_store.py` | 缓存命中/失效、env 覆盖路径、JSON/YAML 写入回读一致性、`invalidate()` 清空所有缓存 | ~80 |
| ChannelManager | `cococat/tests/test_channel_manager.py` | connect 注册实例 + 更新状态、disconnect 清理、auto_reconnect 跳过 disabled/缺凭据频道、重复 connect 替换旧实例 | ~100 |
| Auth | `cococat/tests/test_auth.py` | JWT 签发/验证/过期解析、密码 bcrypt 校验、中间件白名单放行/401 拦截 | ~60 |

```
已有 ConfigStore: 290 行 → 0 tests
已有 ChannelManager: 274 行 → 0 tests
已有 Auth: 81 行 → 0 tests
                          ———
新增测试: ~240 行
```

### 阶段 2: 启动管线（2 个文件）

| 模块 | 文件 | 测试重点 |
|------|------|----------|
| Bootstrap | `cococat/tests/test_bootstrap.py` | 工厂函数独立可测（传入 mock ctx）、resident/worker 从 DB 加载、seed 行为幂等 |
| App lifecycle | `cococat/tests/test_app.py` | `create_app()` 返回 FastAPI 实例、`/api/health` 200、lifespan 启动/停止 worker 和 cron |

### 阶段 3: 核心执行 + 记忆（3 个文件）

| 模块 | 文件 | 测试重点 |
|------|------|----------|
| Agent ReAct | `cococat/tests/test_agent_loop.py` | `_invoke_llm` 分流式/非流式、循环终止（text-only break）、tool 执行后继续迭代、max_iterations 兜底 |
| MemoryStore | `cococat/tests/test_memory_store.py` | remember/recall 基路径、dream 从 session 提取、compile 层级压缩 |
| Session | `cococat/tests/test_session.py` | JSONL 读写、sanitized_read 缓存、append_pair |

### 测试基础设施

不需要新依赖。已有 `pytest` + `pytest-asyncio`。用 `tmp_path` fixture 做临时文件系统。

```python
# 示例：ConfigStore 测试骨架
@pytest.fixture
def store(tmp_path):
    return ConfigStore(config_dir=str(tmp_path / "config"))

def test_get_auth_caches(store):
    store.set_auth("openai", "sk-123")
    assert store.get_auth("openai") == "sk-123"
    # 验证二次读取从缓存返回（不重新读文件）

def test_env_override_ignores_default_path(store, monkeypatch):
    monkeypatch.setenv("COCOCAT_AUTH_FILE", "/tmp/custom-auth.json")
    # 验证 auth_path 属性使用 env override
```

---

## Line B: 迁移治理

### 问题

`cococat/db/database.py:11-133` — 133 行 `SCHEMA` 字符串常量。改字段靠 `_migrate_scenes_table()` 手写 `PRAGMA table_info` 检测。

### 方案

引入 **Alembic**（SQLAlchemy 的迁移工具，CocoCat 已经依赖 SQLAlchemy 通过 `sqlite3` + `pandas` 间接使用过，但数据库层用的是原生 `sqlite3` —— 这不需要 SQLAlchemy ORM，仅用 Alembic 的迁移引擎）。

**如果不引入新依赖**，用自建轻量方案：

```
cococat/db/migrations/
├── __init__.py
├── 001_initial_schema.sql
├── 002_add_facts_fts5.sql
├── 003_add_todos_table.sql
└── _apply.py           # 读取 __version__ 表，顺序执行未应用的迁移
```

`Database` 构造函数末尾调用 `apply_migrations(self._conn)`。

每条迁移是一个 `.sql` 文件 + 一个可选的 Python 脚本（用于数据迁移）。`_apply.py`：

```python
def apply_migrations(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS __migrations__ (version INT PRIMARY KEY, applied_at TEXT)")
    applied = {r[0] for r in conn.execute("SELECT version FROM __migrations__")}
    for entry in sorted_migrations():
        if entry.version not in applied:
            conn.executescript(entry.sql)
            conn.execute("INSERT INTO __migrations__ (version, applied_at) VALUES (?, ?)",
                         (entry.version, datetime.now().isoformat()))
            conn.commit()
```

### 迁移内容

将现有 `SCHEMA` 字符串拆为 3 个迁移文件：

- `001` — agents, scenes, messages, tasks (初始创建)
- `002` — facts + FTS5, dag_runs, todos
- `003` — scenes 表后来的字段变更（合并 `_migrate_scenes_table()`）

---

## Line C: ADR 记录

Phase 1 的 6 项决策写入 `docs/adr/`：

| ADR | 决策 | 原因 |
|-----|------|------|
| 001 | 消除 get_ctx_static | 全局状态阻塞测试；14 个调用点全部改为显式参数注入 |
| 002 | ConfigStore 为 auth 单源 | CredentialManager 独立缓存 auth.json 导致 API 写入后不一致 |
| 003 | 路径集中注册 | 32+ 处硬编码路径 → ConfigStore 属性 + 环境变量覆盖 |
| 004 | ReAct 流式/非流式分支合并 | `_invoke_llm` 封装两种调用模式；循环体从 50 行缩至 15 行 |

---

## 执行顺序

```
Phase 2a (本周)
├── ConfigStore 测试
├── ChannelManager 测试
├── Auth 测试
└── 迁移系统搭建

Phase 2b (下周)
├── Bootstrap 测试
├── App 测试
└── ADR 001-004

Phase 2c (后续)
├── Agent ReAct 测试
├── MemoryStore 测试
├── Session 测试
└── 迁移文件 001-003
```

---

## 验收标准

- [ ] `pytest --cov=cococat/config_store --cov=cococat/core/channel_manager --cov=cococat/auth` 覆盖率 > 80%
- [ ] 迁移系统支持 `python -m cococat.db.migrate` 命令（显示迁移状态 / 执行待应用迁移）
- [ ] `docs/adr/` 下有 4 个 ADR 文件
- [ ] 测试总数从 248 增长到 280+
