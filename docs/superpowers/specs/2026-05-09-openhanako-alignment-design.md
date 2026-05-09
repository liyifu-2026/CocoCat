# OpenHanako Alignment Design

**Date:** 2026-05-09  
**Status:** Design Approved  
**Reference:** `references/openhanako/`

## Summary

取长补短，将 CocoCat 与 OpenHanako 的优秀实践对齐。共 6 个 Phase，每个 Phase 建立在上一 Phase 基础上，总工期约 20 周。

| Phase | 内容 | 工期 |
|-------|------|------|
| 1 | 环境隔离 + ESLint 架构约束 | Week 1-2 |
| 2 | 依赖注入 (DI) | Week 3-5 |
| 3 | SessionFile 统一文件注册 | Week 5-7 |
| 4 | Zustand 状态管理迁移 | Week 7-9 |
| 5 | 测试覆盖 40 → 200+ | Week 9-13 |
| 6 | 插件 SDK | Week 13+ |

依赖链：`1 → 2 → 3 → 6` 和 `1 → 2 → 5`，`4` 可与 `3` 并行，`6` 站在全部基础上。

---

## Phase 1: 环境隔离 + ESLint（Week 1-2）

### 1A. 环境隔离

**问题：** 当前所有数据（agents/、scenes/、chat/、knowledge/）落在项目根目录，开发和生产共用同一份。切换环境需改 .env 20 行。

**设计：** 借鉴 OpenHanako 的 `~/.hanako` / `~/.hanako-dev` 模式。

```
COCOCAT_ENV=dev   →  ~/.cococat-dev/
COCOCAT_ENV=prod  →  ~/.cococat/
COCOCAT_ENV=leaif →  ~/.cococat-leaif/   (多开发者共存)
```

| 端 | 文件 | 改动 |
|----|------|------|
| Rust | `src/config.rs` | 新增 `data_dir()` 函数，从 `COCOCAT_ENV` 推导路径 |
| Rust | `src/main.rs` | DB/agents/scenes 路径用 `data_dir()` |
| Python | `py-agent/context.py` | 同理加 `get_data_dir()` |
| Python | `web/main.py` | 同理 |
| Script | `start.sh` | 加 `export COCOCAT_ENV=dev` |
| Config | `.env.example` | 加 `COCOCAT_ENV=dev` |

启动时检测旧路径有数据，提示迁移。

### 1B. ESLint 架构约束

**问题：** 当前无模块边界强制，`web/routes/` 可直接 import `py-agent/` 内部模块。

**设计：** 借鉴 OpenHanako 的 `no-restricted-imports` 规则。

| # | 规则 | 工具 |
|---|------|------|
| 1 | `web/routes/` 禁止 import `py-agent/` 内部模块 | ruff (Python) |
| 2 | `py-agent/tools/` 禁止 import `py-agent/channels/` | ruff |
| 3 | `src/api/` 禁止直接 import `src/agent/process.rs` | clippy 或文档 |
| 4 | `web-ui/src/pages/` 禁止直接 import `api/` 模块 | ESLint |
| 5 | `py-agent/providers/` 禁止 import `agent_runtime.py` | ruff |

**验收：**
- `COCOCAT_ENV=dev ./start.sh` → 数据在 `~/.cococat-dev/`
- 违规跨层 import → CI 红

---

## Phase 2: 依赖注入（Week 3-5）

### 2A. Python Agent Service Container

**问题：** `agent_loop.py` 直接 `from providers.factory import get_provider`，测试无法 mock。

**设计：** 创建 `py-agent/container.py`：

```python
@dataclass
class AgentServices:
    provider_factory: ProviderFactory
    tool_registry: ToolRegistry
    skill_hub: SkillHub
    scene_manager: SceneManager
    sandbox: Sandbox | None
    config: dict

    @classmethod
    def from_env(cls) -> "AgentServices": ...
    @classmethod
    def test_double(cls, **overrides) -> "AgentServices": ...
```

| 文件 | 改动 |
|------|------|
| `agent_runtime.py` | 启动时创建 `AgentServices.from_env()`，注入 `agent_loop` |
| `agent_loop.py` | `AgentLoop.__init__` 接收 `services: AgentServices` |
| `tools.py` | 工具函数接收 `services` 参数 |
| `channels/*.py` | 渠道构造函数接收 `services` |

### 2B. Python Web Service Container

**问题：** `web/routes/` 直接调用 agent 内部方法，跨层耦合。

**设计：** `web/services/container.py` — `WebServices` 封装所有后端交互。FastAPI 路由用 `Depends(get_web_services)` 注入。

```python
@router.get("/agents")
async def list_agents(
    services: WebServices = Depends(get_web_services)
):
    return await services.agent_executor.list_agents()
```

### 2C. Rust AppState 拆分

**问题：** `AppState` 是一个大结构体（6 个字段），handler 不关心也用不到全部。

**设计：** 拆为 4 个独立 `Extension`：`db_pool`、`ws_tx`、`dispatch_tx`、`jwt_state`。Handler 只 extract 需要的。

---

## Phase 3: SessionFile 统一注册（Week 5-7）

**问题：** 文件路径散落在 `channels/wechat.py`、`channels/telegram.py`、`web/routes/chat.py`、`tools.py` 四处，多渠道下文件身份不一致。

**设计：** 借鉴 OpenHanako 的 SessionFile 模式。

```python
class SessionFileRegistry:
    def register(session_id, channel, filename, data: bytes) -> SessionFile
    def get(file_id) -> SessionFile | None
    def list_by_session(session_id) -> list[SessionFile]
    def update(file_id, new_data: bytes) -> SessionFile
    def delete(file_id)
    def by_checksum(checksum) -> SessionFile | None  # 去重
```

- 元数据通过 DI 注入（生产用 SQLite，测试用内存 dict）
- 物理文件：`~/.cococat/{env}/files/{id[:2]}/{id}`
- 所有文件读写必须经过 Registry——Phase 1 的 ESLint rule 会禁止直接 `open()`

**改造范围：** `channels/telegram.py`、`channels/wechat.py`、`web/routes/chat.py`、`tools.py` 的文件操作全部走 registry。

---

## Phase 4: Zustand 状态管理迁移（Week 7-9）

**问题：** 8 个 Context 全是单一大对象，一个字段变就全局重渲染。Dashboard 套 5 层 Provider。

**设计：** 7 个 Zustand Store 替代 8 个 Context。

```
原 Context                     →  新 Zustand Store
AuthContext                    →  auth-store.ts
ThemeContext + LanguageContext →  preference-store.ts (persist)
SidebarContext + PanelContext  →  ui-store.ts
BreadcrumbContext              →  ui-store.ts
DialogContext                  →  dialog-store.ts
LiveUpdatesContext             →  live-store.ts
(新)                            →  agent-store.ts
(新)                            →  scene-store.ts
```

React Query 不动——继续管服务端状态。Zustand 只管客户端状态。

**验收：** `MetricCard` 用 `useLiveStore(s => s.agentCount)`——只有 agentCount 变才 render。

---

## Phase 5: 测试覆盖（Week 9-13）

**为什么此时做：** Phase 2 的 DI 使 mock 无痛，Phase 1 的 ESLint 会拦有问题测试，Phase 4 的 Zustand store 可直接测（无 React tree）。

| 端 | 当前 | 目标 | 关键变化 |
|----|------|------|----------|
| Rust | 1 文件 | 30+ 文件 | SQLite `:memory:` + 拆分后的 Extension |
| Python | 40 文件 | 120+ 文件 | `AgentServices.test_double()` 注入 mock |
| 前端 | 0 文件 | 50+ 文件 | Zustand store 纯函数测 |
| E2E | 待开发 | 13+ 文件 | Playwright |

**验收：** `cargo test`、`pytest`、`npx vitest`、`npx playwright test` 全部通过。

---

## Phase 6: 插件 SDK（Week 13+）

### 插件能贡献

| 类型 | 实现端 | 例子 |
|------|--------|------|
| 工具 | Python | Notion API 工具 |
| 渠道 | Python | Slack 渠道 |
| 技能 | Markdown | 客服技能 |
| Provider | Python | 新 LLM 接入 |
| 前端 widget | React + iframe | Dashboard 侧边面板 |
| 定时任务 | Python | 日报 |

### 4 个 SDK 包

```
packages/
├── plugin-protocol/       ← 清单格式、权限枚举、消息类型
├── plugin-runtime/        ← Python: PluginBase 基类、@tool 装饰器
├── plugin-sdk/            ← TypeScript: iframe→host 通信
└── plugin-components/     ← React: <PluginCard> 等组件
```

### manifest.json

```json
{
  "name": "notion-integration",
  "version": "1.2.0",
  "permissions": ["network:api.notion.com", "file:read"],
  "contributes": {
    "tools": ["notion_page_write", "notion_page_read"],
    "skills": ["notion.skill.md"],
    "widget": "widget/index.html"
  }
}
```

权限级别：`restricted`（只读文件+限定域名）| `full-access`（明确信任）。

### 安全模型

- 文件访问走 Phase 3 SessionFileRegistry（不是直接 `open()`）
- 网络走域名白名单
- UI 用 iframe `sandbox` 属性隔离
- 权限在 PluginManager 加载时注入受限的 `AgentServices` 子集

### 执行节奏

```
Week 13-14: plugin-protocol + plugin-runtime
Week 15-16: PluginManager + plugin-sdk (iframe通信)
Week 17-18: plugin-components + 重构 mcp/image-gen 为插件
Week 19-20: 安装流程、示例插件、文档
```

---

## Risk Assessment

| Phase | 风险等级 | 理由 |
|-------|----------|------|
| 1 | 低 | 不改变运行逻辑，只加路径和 lint 规则 |
| 2 | 中 | 改动 ~15 个 Python 文件，但每个改动小（加参数） |
| 3 | 低-中 | 新增 registry 层，底层文件系统不变 |
| 4 | 中 | 改 18 个页面 28 个组件，但每个改动机械化 |
| 5 | 低（持续） | 加测试不破功能，是持续投入 |
| 6 | 高 | 大功能，依赖全部前置 Phase |
