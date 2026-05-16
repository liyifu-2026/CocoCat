# KB Agent Activation Design

**Date**: 2026-05-16
**Status**: Draft
**Context**: KB 基础设施已建成，但未完全激活——agent 侧无检索工具、维护管线未连线、无专属管理员。本文定义如何将 KB 从「被动文件存储」激活为「自主运转的知识系统」。

---

## 1. Motivation

当前 KB 的差距：

| 类别 | 现状 |
|------|------|
| Agent 工具 | 其他 agent 只有 system prompt 里的 KB overview，无法主动检索。没有 search_kb 工具。 |
| 维护管线 | Dedup、lint、overview、cascade delete、image pipeline 代码已写好，但无触发入口。 |
| 专属管理员 | 无 agent 专门负责 KB。上传 ingest 由 Worker 直接调用 IngestPipeline，不走 agent 决策。 |
| 前端 | 无文件上传 UI，无 kb-agent 对话入口。 |

目标：全面激活 KB，让 kb-agent 成为知识库的专属管理员。

---

## 2. Agent Hierarchy Redesign

从 MAIN/SUB 二元改为 Resident/Worker 二级：

```
Resident Agent（常驻 · 平级）
├── Coco        → 绑定 /chat，编排 & 对话
├── kb-agent    → 绑定 /knowledge，知识库管理
└── 未来：Scene Agent → 1:1 深度绑定场景页面

Worker Pool（临时执行池）
└── 触发即创建，完成即销毁，通用执行工具（bash/file/browser...）
```

**关键规则**：
- Resident agent 之间平级，无主从，各自独立负责一个领域，1:1 深度绑定到各自页面
- Resident agent 不互相「分发/派发」——各自决定是否调 Worker 池
- Worker 无 UI 入口，对用户不可见

---

## 3. KBService — 统一服务层

将散落在 `ingest/*.py` 的能力封装为 `cococat/kb/service.py`，不依赖 LLM/HTTP，纯函数可测试。

```python
class KBService:
    # ── 查询（供所有人） ──
    search(kb_name, query, limit=20) → list[SearchResult]
    read(kb_name, type, slug) → WikiPage | None
    list_pages(kb_name) → dict[list[str], list[str]]
    get_graph(kb_name) → GraphResult  # {nodes, links, insights}

    # ── 写入（仅 kb-agent） ──
    write_page(kb_name, type, slug, content, frontmatter) → None
    cascade_delete(kb_name, source_filename) → CascadeResult

    # ── 维护（仅 kb-agent） ──
    run_dedup(kb_name, llm) → DedupResult
    run_lint(kb_name) → LintResult
    gen_overview(kb_name, llm) → str

    # ── 注入 ──
    get_overview_context(kb_names) → str
```

**与现有代码关系**：薄封装，不重写。IngestPipeline 保留现有流程。

---

## 4. Agent Tools

### 4.1 kb-agent（Resident，读写）

| Tool | 功能 |
|------|------|
| search_kb | 全文搜索 wiki 页面 |
| read_wiki | 读取指定页面 |
| write_wiki | 创建/覆盖 wiki 页面 |
| run_dedup | 运行去重管线 |
| run_lint | 健康检查（孤儿页/断链/缺 frontmatter） |
| gen_overview | 生成/更新 KB 全局概览 |
| cascade_del | 级联删除源文件及关联页面 |
| get_graph | 知识图谱 + 洞察（连接/缺口/桥梁） |
| call_worker | 调用 Worker 池执行耗时任务 |

每个工具是 KBService 方法的薄封装，不含业务逻辑。

### 4.2 其他 Resident Agent（只读）

| Tool | 功能 |
|------|------|
| search_kb | 全文搜索 wiki 页面 |
| read_wiki | 读取指定页面 |

Coco 也拥有这两个只读工具。

### 4.3 Worker Agent（只读）

| Tool | 功能 |
|------|------|
| search_kb | 全文搜索 wiki 页面 |
| read_wiki | 读取指定页面 |

---

## 5. kb-agent Configuration

```yaml
# config/residents/kb-agent.yaml
id: kb-agent
name: 知识库管理员
role: resident
page: /knowledge
skills: [knowledge-ingestion]
tools: [search_kb, read_wiki, write_wiki, run_dedup, run_lint,
       gen_overview, cascade_del, get_graph, call_worker]
cron:
  - name: lint
    schedule: "@daily"       # 每天健康检查
  - name: dedup
    schedule: "@weekly"      # 每周去重
  - name: overview
    schedule: "@weekly"      # 每周刷新概览
```

---

## 6. knowledge-ingestion Skill

位置：`skills/public/knowledge-ingestion.md`

内容要点：
- 材料分析：识别类型（文档/代码/对话/图片），提取关键实体和概念，判断与现有 wiki 重叠度
- 注入策略：新实体→ entities/，新概念→ concepts/，已有页面补充→ merge，使用 wikilink `[[slug]]` 建立关联
- 质量控制：检查 frontmatter 完整性，去重检查，更新 index.md + log.md

---

## 7. Trigger Mechanisms

### 7.1 事件驱动（即时）

- 用户上传文件 → 保存到 raw/sources/ → 推送 `source_uploaded` 事件给 kb-agent
- 用户在前端对话窗发指令 → 直接路由给 kb-agent
- 用户删除源文件 → 推送事件 → kb-agent 决定是否 cascade

### 7.2 Cron 定时巡检

```python
class CronTaskRunner:
    """每个 Resident agent 可注册 cron 表达式，直接调用 agent"""
    def tick(self):
        for resident in self.residents:
            for job in resident.cron_jobs:
                if job.is_due():
                    resident.handle_cron(job)
```

不引入外部 cron 库。CronTaskRunner 与现有 TaskWorker 合并到同一后台循环。

### 7.3 Worker 调用

Resident agent 通过 `call_worker` 工具调用 Worker 池执行耗时操作（如 ingest）：

```
kb-agent → call_worker(task="ingest file X into KB Y", context={...})
→ Worker Pool 分配空闲 Worker 执行
→ 返回结果
```

---

## 8. Frontend

### 8.1 KB 详情页布局

```
┌──────────────────────────────────────────────┐
│  📚 knowledge/team-wiki                       │
│  ┌────────────┬─────────────────────────────┐ │
│  │ Entities   │ Wiki 页面内容（Markdown）    │ │
│  │ Concepts   │                             │ │
│  │            │                             │ │
│  └────────────┴─────────────────────────────┘ │
│                         ┌───────────────────┐ │
│                         │ 🤖 kb-agent       │ │
│                         │ 对话小窗           │ │
│                         └───────────────────┘ │
└──────────────────────────────────────────────┘
```

左侧：现有 Wiki 浏览（KnowledgeDetail.tsx）。右侧：新增 kb-agent 对话小窗。

### 8.2 上传 UI

在 Knowledge 页面加入上传按钮 + 文件选择 → POST /api/knowledge/{kb}/upload → 显示进度。

### 8.3 知识图谱洞察

在 KnowledgeDetail 侧边栏展示 get_graph 返回的 insights（surprising connections、knowledge gaps、bridge nodes），利用现有的 KnowledgeGraph 能力。

---

## 9. Data Flow Summary

```
用户上传文件
  → POST /api/knowledge/{kb}/upload
  → 保存 raw/sources/
  → 推送事件给 kb-agent
  → kb-agent 评估 → 简单: call_worker(ingest) / 复杂: 亲自处理

用户与小窗对话
  → HTTP/WS → kb-agent
  → kb-agent 自行决定: 直接回答 / call_worker / 调 KB 工具

Cron 触发
  → CronTaskRunner.tick() → kb-agent.handle_cron("lint")
  → kb-agent 调用 run_lint → 有问题则 call_worker 修复

Worker 查 KB
  → 调用 search_kb / read_wiki（只读）
```

---

## 10. Testing Strategy

### 单元测试（无 LLM）

| 测试 | 文件 |
|------|------|
| KBService.search/read/write/list | `tests/cococat/test_kb_service.py` |
| KBService.run_lint（孤儿页/断链/缺 frontmatter） | 同上 |
| KBService.cascade_delete | 同上 |
| KBService.get_graph（节点/边/洞察） | 同上 |
| CronTaskRunner（表达式/is_due） | `tests/cococat/test_cron_runner.py` |
| Agent 工具注册（kb-agent 9 工具 / Worker 2 只读） | `tests/cococat/test_agent_roles.py` |

### 集成测试（Mock LLM）

| 测试 | 文件 |
|------|------|
| 端到端 ingest（扩展已有） | `tests/cococat/test_kb_integration.py` |
| kb-agent 对话（搜索/写入） | 同上 |
| Worker 只读权限校验 | 同上 |
| Cron lint/dedup 流程 | `tests/cococat/test_cron_runner.py` |

---

## 11. Implementation Order

1. **KBService** — 封装现有能力为 service.py，写单元测试
2. **Agent hierarchy** — AgentRole 改为 RESIDENT/WORKER
3. **kb-agent 注册** — config + 工具注册 + skill 文件
4. **CronTaskRunner** — 与 Worker 主循环合并
5. **前端对话窗** — KB 页面右侧小窗
6. **前端上传 UI** — 上传按钮 + 进度
7. **集成测试** — 端到端验证
