# CocoCat 交互体验重构 · 设计规格

**日期**：2026-05-20
**版本**：v2.0（基于底层重构后的完整规格）
**底层模型参考**：`docs/superpowers/specs/2026-05-20-core-model-analysis.md`

---

## 1. 概述

### 1.1 目标

对 CocoCat 前端进行全面交互体验重构。核心原则：**安静中带着温度**——专业为底，品牌个性点睛。

### 1.2 产品核心模型（已确认）

```
CocoCat = Coco（一只猫）+ sub_agent（分身工具）+ Scene（工作房间）+ Mode（人格帽子）
```

- **Coco**：唯一智能体。用户对话、调度 sub_agent、管理一切。临时创建，用完销毁。
- **Mode**：Coco 的「帽子」——一套 prompt + tools + skills。主人格（日常通用）+ kb-admin（知识库管理）。系统自动或手动切换。
- **Scene**：Coco 的「房间」——独立的 context + KB + channels + 记忆隔离。团队共享。
- **sub_agent**：Coco 的工具。Coco 调用它 fork 临时 worker 执行具体任务，继承当前 Mode（或 Coco 指定 Mode），执行完销毁。

### 1.3 用户旅程

```
登录(Login) → 首次亮灯(Welcome) → 了解工作室(Onboarding) →
工作室总览(Dashboard) → 对话(Chat) / 管理场景(Scenes) / 浏览资料(Knowledge)
```

### 1.4 页面清单（最终版）

**保留重做（11 个）：**
| # | 页面 | 路由 | 说明 |
|---|------|------|------|
| 1 | Login | /login | 太极构图 + 猫微交互 |
| 2 | Welcome | / (首次) | 空工作室首次亮灯 |
| 3 | Onboarding | /onboarding | 2-3 步引导 |
| 4 | Dashboard | /dashboard | 工作室总览：Coco 状态 + sub_agent 快照 + 活动 + Scene 信息 |
| 5 | Chat | /chat | 对话 + Mode 选择器 + sub_agent 调用展示 |
| 6 | Scenes | /scenes | 场景管理 |
| 7 | SceneNew | /scenes/new | 创建场景 |
| 8 | Knowledge | /knowledge | KB 管理 |
| 9 | KnowledgeDetail | /knowledge/:kb | Wiki 浏览器 |
| 10 | MemoryBrowser | /memory | 记忆浏览 |
| 11 | SystemStatus | /status | 系统健康 |

**非独立页面（嵌入式/浮层，5 个）：**
| 类别 | 说明 |
|------|------|
| ChatHistory | Chat 内左侧面板 |
| FileBrowser | Chat 内上下文面板 |
| NotificationCenter | 全局通知面板 |
| GlobalSearch | ⌘K 命令面板 |
| Mode 选择器 | Chat 内组件 |

**已砍页面（7 个）：**
Agents / DAGWorkbench / TimelineReplay / Studio / SceneRun / SceneDetail（并入 Scenes 管理）/ 「我的 Coco」（被 Mode 替代）

---

## 2. 视觉风格规范

### 2.1 品牌 Logo

- 圆形构图，橘猫沿太极 S 弧跃起。猫色 `#f97316`（纯橘）。
- 纯白背景，无渐变/阴影/描边。UI 中猫的存在感：中——Coco 是 Main AI，出现在 Login、Welcome、Dashboard 调度台，不是吉祥物。

### 2.2 配色体系

| Token | 明色 | 暗色 | 用途 |
|-------|------|------|------|
| Primary | `oklch(0.56 0.10 30)` ~ #e07b5a | `oklch(0.60 0.15 30)` | 主交互色 |
| Logo Orange | `#f97316` | — | 品牌点缀 |
| Secondary | `oklch(0.55 0.065 135)` | `oklch(0.60 0.065 135)` | 成功/完成 |
| Tertiary | `oklch(0.65 0.09 75)` | `oklch(0.70 0.09 75)` | 警告/高亮 |
| Background | `oklch(0.965 0.006 75)` | `oklch(0.145 0.004 50)` | 页面底色 |

### 2.3 明暗双模式平等

所有页面和组件在两种模式下完整测试。暗色下光晕 `mix-blend-mode: screen`。

### 2.4 字体层级

| Token | 字号 | 字体 | 用途 |
|-------|------|------|------|
| Display XL | 2rem | Zen Antique | Welcome 标题 |
| Display LG | 1.5rem | Zen Antique | 页面标题 |
| Heading | 1.125rem | Noto Sans SC | 区块标题 |
| Subheading | 1rem | Noto Sans SC | 卡片标题 |
| Body | 0.875rem | Noto Sans SC | 正文 |
| Caption | 0.75rem | Noto Sans SC | 标签/元数据 |
| Code | 0.8125rem | JetBrains Mono | 代码 |

### 2.5 氛围层

保持三层：`bg-warm-glow`（右上暖光）+ `bg-warm-glow-left`（左下暖光）+ `bg-noise`（SVG 噪点纹理）。

---

## 3. 页面格式文档模板

每页 spec 包含 8 个维度：

1. 概述（目的、场景、层级）
2. 路由与导航
3. 页面布局（线框图级）
4. 组件树
5. 状态设计（Loading/Empty/Error/Edge cases）
6. 数据流（API + react-query + WebSocket）
7. 交互细节（动画/快捷键/拖拽）
8. i18n keys

---

## 4. 已确认的页面前端格式

### 4.1 #1 Login

**方向**：太极之门 + 猫微交互（D：A+B 混合）。左实右虚分屏，猫眼随光标，输密码时猫捂眼。

### 4.2 #2 Welcome

**方向**：Coco 在调度台就位，空工作室俯视图。其余工位虚线圈，资料架空书架。双路径：添加 Scene / 直接进 Chat。

### 4.3 #3 Onboarding

**方向**：三步——起名(可选跳)→ 了解 Scene → 进入工作室。不可创建 Agent（已砍），改为了解 Scene 概念。

---

## 5. 待确认的页面

以下页面已列清单，前端格式文档尚未逐一讨论：

- #4 Dashboard（需基于最新底层模型重设计）
- #5 Chat（需加 Mode 选择器 + sub_agent 展示 + 历史面板）
- #6 Scenes / #7 SceneNew
- #8 Knowledge / #9 KnowledgeDetail
- #10 MemoryBrowser
- #11 SystemStatus

以及嵌入式组件：ChatHistory、FileBrowser、NotificationCenter、GlobalSearch、Mode 选择器。

---

## 6. 遗漏补充：12 个体验维度

| # | 维度 | 现状 | 需要的改进 |
|---|------|------|-----------|
| A | 空态设计体系 | EmptyState 组件存在但未统一使用 | 所有页面空态统一 |
| B | 加载态/骨架屏 | LoadingSkeleton 存在但使用不充分 | 全局加载策略 |
| C | 错误态+降级 | ErrorState/ErrorBoundary 需整合 | WebSocket/API/权限 |
| D | 移动端 | MobileBottomNav 存在但未适配 | 明确移动端策略 |
| E | 无障碍 (a11y) | Radix 有基础支持 | 审核覆盖率 |
| F | 快捷键+⌘K | cmdk 已安装未启用 | 全局命令面板 |
| G | 通知系统 | sonner 已集成 | 通知中心 |
| H | Settings 重构 | 12 Tab 平铺 | 分类重组 |
| I | 连接状态 UX | WS 可能静默失败 | 连接指示器 |
| J | 功能发现 | 无 | spotlight + 更新日志 |
| K | 页面过渡动画 | 路由切换无过渡 | 统一转场策略 |
| L | i18n 覆盖率 | 385+ key | 新页面全覆盖 |

---

## 7. 技术约束

- React 19 + Vite 8 + TypeScript 6
- shadcn/ui (New York) + Tailwind CSS 4 + OKLCH
- React Query + WebSocket
- 无需新增依赖（DAG 砍了不再需要 dagre/elkjs；Studio 砍了不再需要 @dnd-kit）

---

## 8. 附录：当前代码相关文件

| 文件 | 说明 |
|------|------|
| `web-ui/src/App.tsx` | 路由定义（需重写） |
| `web-ui/src/pages/Chat.tsx` | 主聊天页（646行，需拆分重构） |
| `web-ui/src/pages/Dashboard.tsx` | 占位（7行，需从零重做） |
| `web-ui/src/components/SceneRail.tsx` | 场景侧栏（需调整） |
| `web-ui/src/components/Layout.tsx` | 全局布局 |
| `web-ui/src/index.css` | 全局样式 + 动画 + CSS 变量 |
| `web-ui/src/components/ui/` | shadcn/ui 23 个组件 |
| `web-ui/src/i18n/` | 国际化 |
