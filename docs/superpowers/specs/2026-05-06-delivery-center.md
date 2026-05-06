# Delivery Center — Mailbox 重设计

## 概念

Mailbox 从"双向聊天"改为**「交付中心」**——Agent 给 Admin 交作业的收件箱。

| 系统 | Chat | Mailbox |
|------|------|---------|
| 方向 | 双向（Admin ↔ Agent） | 单向（Agent → Admin） |
| 用途 | 紧急沟通、即时讨论 | 交付成果、永久存档 |
| 消息 | 滚动丢失 | 永久保留 |
| 文件 | 不支持 | 支持附件 |
| 结构 | 无结构 | 有主题 + 版本 + 审阅状态 |

## 数据流

```
Admin 在 Chat: "帮我写个优化方案"
    → Agent: "好的"
    → Agent 完成工作
    → Agent 调用 send_delivery() 工具
    → POST /api/deliveries/create
    → 新交付件出现在 Admin 的 Mailbox
    → Admin 审阅 → 批准 / 请求修改
    → Agent 看到结果 → 继续或结束
```

## 数据模型

复用 Rust `deliveries` 表（不修改 schema）：

| 字段 | 用途 |
|------|------|
| `id` | UUID |
| `subject` | 主题 —— 相同 subject 自动归为同一包裹的不同版本 |
| `from_agent` | 发送 Agent |
| `body` | Agent 交付备注 |
| `files` | JSON: `[{name, path, size, mime}]` |
| `status` | `new` / `read` / `approved` / `changes_requested` |
| `created_at` | 时间戳 —— 用于排序和版本顺序 |

**版本规则**: 相同 `subject` + 相同 `from_agent` 的 deliveries 按 `created_at` 排序，最新的最高版本。前端自动归组。

## UI

```
┌──────────────────────────────────────────────────────┐
│  📦 交付中心                      [新交付件 N]       │
├──────────────┬───────────────────────────────────────┤
│  搜索...     │                                       │
│              │  数据库查询优化方案                    │
│  📌 v2       │  v2 · employee_a · 14:32   ✅ 已批准  │
│     数据库   │  ┌────────────────────────────────┐   │
│     approved │  │ 📄 optimization_report.md      │   │
│              │  │    12 KB · 2026-05-06          │   │
│  📌 v1       │  │ 📄 query_patch.diff            │   │
│     首页重构  │  │    3 KB · 2026-05-06          │   │
│     pending  │  └────────────────────────────────┘   │
│              │                                       │
│              │  Agent 备注:                           │
│              │  "已完成优化，查询速度提升 5 倍"        │
│              │                                       │
│              │  ── v1 (14:00) ───────────── 3 files  │
│              │                                       │
│              │  [✅批准] [🔄请求修改] [💬继续聊] [📎下载全部]│
└──────────────┴───────────────────────────────────────┘
```

左侧: 包裹列表（按 subject 归组），显示最新版本的状态
右侧: 选中包裹的详情，版本时间线，文件列表，操作按钮

## 改动文件

| 文件 | 改动 |
|------|------|
| `src/api/deliveries.rs` | 新增 `approve_delivery`, `request_changes` handler |
| `src/api/router.rs` | 注册 2 条新路由 |
| `web/main.py` | 新增 `POST /api/deliveries/create` proxy |
| `web-ui/src/pages/Mailbox.tsx` | 完全重写为交付中心 |
| `web-ui/src/api/mailbox.ts` | 适配新 API |
| `web-ui/src/i18n/zh.ts`, `en.ts` | 新增翻译 |
