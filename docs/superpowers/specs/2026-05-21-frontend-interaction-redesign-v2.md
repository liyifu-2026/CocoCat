# CocoCat 前端交互重设计 · v2

**日期**：2026-05-21
**版本**：v2（推翻 2026-05-20 interaction-redesign-design.md）
**对齐参考**：Dribbble shot 22232802 (UI Chat AI GPT character)

---

## 1. 品牌与视觉系统

整个设计严格对齐 Dribbble 参考的视觉语言：深蓝黑底、蓝/琥珀双点缀、圆润大圆角、模糊光晕氛围、Plus Jakarta Sans 字体。

### 1.1 配色

| Token | 值 | 用途 |
|-------|-----|------|
| bg-primary | `#090a0d` | 左侧导航、右侧 Chat 面板底 |
| bg-main | `#0d0f12` | 主容器底 |
| bg-card | `#111318` | 卡片/区块底 |
| bg-input | `#12151c` | 输入框底 |
| bg-bubble | `#151922` | Coco 消息气泡底 |
| border-default | `rgba(255,255,255,0.06)` | 默认边框 |
| border-hover | `rgba(255,255,255,0.10)` | hover 边框 |
| border-active | `rgba(59,130,246,0.3)` | 激活边框 |
| accent-blue | `#3b82f6` / `#60a5fa` | 主点缀（按钮、链接、激活态） |
| accent-amber | `#f59e0b` / `#d97706` | 辅点缀（kb-admin mode、星级、border accent） |
| accent-purple | `#6366f1` | 思考态/工具调用 |
| text-primary | `#f3f4f6` | 主文字 |
| text-secondary | `#9ea4b0` | 次要文字 |
| text-muted | `#667` / `#556` / `#444` | 三级/辅助文字 |

### 1.2 字体

| 用途 | 字体 | 字重 | 字号 |
|------|------|------|------|
| 页面标题 | Plus Jakarta Sans | 600 | 15px |
| 卡片/区块标题 | Plus Jakarta Sans | 500 | 10-11px |
| 正文 | Plus Jakarta Sans | 400 | 11-12px |
| 辅助文字/标签 | Plus Jakarta Sans | 400 | 9-10px |
| 聊天气泡 | Plus Jakarta Sans | 400 | 11px |
| 代码/monospace | JetBrains Mono | 400 | 11px |

### 1.3 形状

- 大圆角体系：容器 `rounded-2xl` (16px)、卡片 `rounded-xl` (12px)、按钮/输入框 `rounded-xl` (12px)、标签 `rounded-full`
- 没有尖角、没有直角矩形

### 1.4 氛围层

- 背景光晕：蓝色 `radial-gradient`（opacity 0.10-0.15）置于左上，琥珀/紫色（opacity 0.10）置于右下
- 模糊光晕：`blur-[120px]`，`pointer-events-none`
- 卡片/面板边框：半透明白色 `rgba(255,255,255,0.06)`，hover 时微微提亮
- 无噪点纹理（与旧 spec 不同）

### 1.5 品牌标识

- 顶部使用纯文字 "CocoCat" 作为品牌标识，Plus Jakarta Sans 600，字间距 tracking-wide
- 无吉祥物、无头像、无拟人化元素
- 品牌个性通过配色、圆角、动效表达

---

## 2. 布局架构

### 2.1 三栏骨架

```
┌──────────┬───────────────────────────┬──────────┐
│   导航   │    操作演示区              │  对话区   │
│  (固定)  │    (Mode 驱动)            │  (始终)  │
│          │                          │          │
│   76px   │     flex-1               │  380px   │
│  #090a0d │     #0d0f12             │  #090a0d │
└──────────┴───────────────────────────┴──────────┘
```

- 左侧导航栏：76px 宽，固定<br/>（窄空间无法放置 "CocoCat" 全称，使用 "CC" 缩写文字标）
- 中间操作演示区：flex-1，响应式
- 右侧对话区：380px 宽（可扩展至 420px），固定
- 三栏之间用 `border-r/l border-gray-800/50` 分割

### 2.2 左侧导航

从上到下排列：
- CocoCat 文字标（顶部 logo，可点击回到首页）
- 💬 Chat — 激活态 bg-blue-600 圆形 icon
- 📁 Scenes — 默认灰色，hover 亮
- 📚 Knowledge — 同上
- 🧠 Memory — 同上
- ⚙ Settings — 同上
- 底部：用户头像（圆形，在线绿点）

导航项使用 44×44px 圆角方块，激活态蓝色填充。

### 2.3 登录页（三栏布局前）

在进入三栏之前，先经过独立全屏登录页：

- 深蓝黑底 + 居中表单
- CocoCat 品牌文字 + 简短描述
- 用户名 / 密码输入 + 登录按钮
- 与三栏采用同一配色体系，视觉衔接自然
- 登录成功 → 平滑过渡进入三栏 Chat 视图

### 2.4 移动端策略

三栏布局为桌面优先设计。移动端降级策略：

- 默认显示对话区（全屏）
- 底部 Tab Bar 切换：Chat / 操作演示区
- 操作演示区作为独立全屏视图
- 导航和对话区通过手势/Burger 访问
- 详细移动端适配留到 plan 阶段的响应式子任务

### 2.5 右侧对话区

顶部：Coco 名称 + 在线状态圆点 + Mode 标签
中部：消息流（Coco 左对齐蓝色气泡，用户右对齐琥珀气泡）
底部：输入框 + 加号按钮 + 发送按钮 + Mode 标签
输入框下方：Powered by CocoCat 小字

---

## 3. Mode 驱动的操作演示区

操作演示区是 Coco 的「名片 + 遥控器」组合。结构固定为两部分：

```
┌────────────────────┐
│  Coco 名片         │
│  (风格随 Mode 变)  │
├────────────────────┤
│  功能区            │
│  (内容随 Mode 变)  │
└────────────────────┘
```

### 3.1 名片区规范

所有 Mode 共享名片骨架，但配色/文案不同：

- **结构**：居中排列 → Mode 色系大图标 + 名称 + 副标题 + Mode 下拉标签 + 状态文案
- **背景**：Mode 色渐变淡化到透明（`linear-gradient(180deg, <mode-color>/0.12, transparent)`）
- **Mode 标签**：半透明底色胶囊（`bg-<mode-color>/0.15 text-<mode-color>`），可点击下拉切换
- **状态文案**：斜体，一句话描述当前态
- **无头像、无吉祥物**：名片氛围通过配色渐变和排版建立，不依赖角色图像

| Mode | 配色 | 图标 | 名称 | 副标题 | 状态文案示例 |
|------|------|------|------|--------|------------|
| default | blue→indigo | 💬 | Coco | Workshop Operator | "Hello! 12 tools ready." |
| kb-admin | amber→yellow | 📚 | Coco · KB Admin | Knowledge Base Operator | "3 KB active. Tools ready." |

### 3.2 default Mode 功能区

**目地**：日常助手模式下的快捷入口和状态总览。功能区分**空闲态**和**工作态**两种显示。

**空闲态区块：**

**区块 1 — 会话管理**
- 「+ New Session」按钮（虚线边框）
- 最近会话列表（每行：圆点 + 标题 + 时间）
- 当前活跃会话高亮（蓝底）

**区块 2 — 最近活动**
- 时间线格式：Coco 做了什么事 + 时间戳
- 如："Coco analyzed project · 5m ago"

**区块 3 — 快捷操作**
- 标签云形式：点击即发送预设指令到 Chat
- 默认建议：「分析当前项目」「创建新任务」「今日摘要」「清理记忆」

**工作态操作可视化（Coco 正在工作中时，功能区动态切换）：**

| Coco 操作 | 演示区可视化 |
|-----------|------------|
| read_file | 文件卡片展示，代码高亮，当前阅读段高亮 |
| edit_file | 双栏 Diff 视图（左旧右新），变更行绿/红标记，实时更新 |
| execute_bash | 终端输出框，深色底，green 等宽字体，输出逐行追加 |
| glob / 搜索 | 结果列表弹出，匹配项亮起，数量角标 |
| create_session | 会话列表顶部滑入新条目，打字机填入标题 |
| switch_scene | Scene 名片区切换，过渡动画 |
| think / 思考 | 紫色脉冲边框卡片，思考内容逐段追加 |
| sub_agent | 工作卡片出现，显示 sub_agent 名称 + 状态，完成后消失 |

### 3.3 kb-admin Mode 功能区

**目地**：知识库管理的视觉化操作台。书架为**平面商城风**（封面卡片平铺）。空闲态展示书架 + 操作日志，工作态实时跟随 Coco 的 KB 操作。

**空闲态区块：**

**区块 1 — 可视化书架**
- 平面卡片风格（类图书商城），封面色块 + 书名 + 分类
- 按分类分组，每个分类有标题 + 书籍计数
- 每行 3-4 张卡片平铺，overflow-x scroll
- 卡片 hover 浮起，点击进入内容预览
- 底部：「+ 新建知识库分类」

**区块 2 — 操作日志**
- 最近 KB 操作列表（Coco 做了什么 KB 相关的事）
- 每行：状态图标 + 操作描述 + 时间

**区块 3 — KB 快捷操作**
- 标签云：「上传文档」「创建 Wiki」「查重/去重」「全文检索」「导出」

**工作态操作可视化（书架实时跟随 Coco 操作）：**

| Coco 操作 | 书架可视化 |
|-----------|-----------|
| 打开一本书 | 目标卡片高亮 → 展开为内容预览区（文章片段 + 滚动位置标记） |
| 阅读滚动 | 内容预览区跟随滚动，正在读的段落高亮行 |
| 创建新条目 | 虚线空卡片滑入书架 → 书名逐字敲入 → 变实色完成 |
| 编辑/修改 | 卡片翻开 → 双栏 diff（左旧右新），变更实时打标 |
| 追加/写入 | 卡片下方内容区逐行追加新段落（打字机效果） |
| 上传文档 | 新卡片从顶部落入书架 → 显示解析进度条 → 完成亮起 |
| 查重扫描 | 书架卡片按相似度重排，重复项脉冲闪烁标记 |
| 删除条目 | 目标卡片缩小淡出消失 |
| 全文检索 | 匹配卡片亮起、不匹配变灰暗 |
| 目录操作 | 卡片展开为树形目录结构，更新项闪烁 |
| 批量操作 | 多张卡片同时激活边框，变更同步刷新 |

### 3.4 操作可视化引擎

**核心原则**：操作演示区是 Coco 的「直播画面」。WebSocket 推送工具调用事件 → 前端解析事件类型 → 动态切换演示区内容。

**通信流**：
```
Coco tool call (websocket)
    → { type: "tool_start", payload: { tool: "edit_file", args: {...} } }
    → 前端匹配操作可视化表 → 渲染对应视图
    → { type: "tool_delta", payload: { diff: "..." } }
    → 视图实时更新
    → { type: "tool_end", payload: { result: "..." } }
    → 视图定格完成态，3s 后回到空闲态
```

**过渡策略**：
- 工具调用开始：空闲态内容 fadeOut 0.2s → 工作态视图 fadeIn 0.2s
- 工具调用结束：工作态保持 3s（用户可看到结果）→ fadeOut 回空闲态
- 连续工具调用：无缝切换视图（不回到空闲态），避免闪烁

### 3.5 Mode 切换

- 名片区的 Mode 标签是下拉选择器
- 切换时操作演示区平滑过渡（fade/scale animation）
- 名片配色、图标、功能区块全部随之变化
- 切换不打断对话，Chat 区继续正常工作

---

## 4. 其他导航项下的操作演示区

当非 Chat 的导航项被选中时，操作演示区展示对应内容。

### 4.1 📁 Scenes

- 场景卡片列表（卡片式，每张卡片：名称 + 描述 + 会话数 + 状态）
- 「+ 新建 Scene」按钮
- 点击卡片进入 Scene 详情（演示区内切换）

### 4.2 📚 Knowledge（独立浏览，非 kb-admin mode）

- 知识库列表
- 点击进入 Wiki 浏览器（文章列表 + 内容预览）
- 搜索框

### 4.3 🧠 Memory

- 记忆时间线视图
- 按时间排列的记忆条目

### 4.4 ⚙ Settings

- 设置面板（分类折叠或 Tab 式）
- Theme、Provider、Channel 等配置

---

## 5. 交互细节

### 5.1 对话气泡

- Coco 消息：左对齐，`#151922` 底，`rounded-2xl rounded-tl-none`（左上直角）
- 用户消息：右对齐，`bg-blue-600` 底，`rounded-2xl rounded-tr-none`（右上直角）
- 时间戳在气泡下方，`9px`，`text-gray-600`

### 5.2 工具调用展示

- 收折面板（details/summary），在 Coco 气泡上方
- 标题：「工具调用 (n)」+ 状态图标
- 展开后每行：工具名 + 耗时 + 状态（running/done/error）

### 5.3 思考过程展示

- 同上收折面板，紫色主题
- 标题：「思考过程」+ Brain 图标

### 5.4 输入框

- 圆角 `rounded-xl`
- placeholder: "Aa"
- 左侧加号按钮（附件/文件上传）、右侧发送按钮
- 输入框下方 Mode 标签（显示当前 mode 名）

### 5.5 微交互

- 投票/点赞按钮：点击粒子动画（彩色碎片飘散）
- 消息进场：fadeSlideUp 动画
- 工具状态变更：实时更新（WebSocket 推送）
- 卡片 hover：border 变亮，scale 1.01

### 5.6 Coco 输入中指示器

- 三个跳动的圆点（bounce 动画，delay 0s / 0.2s / 0.4s）
- 显示在左侧气泡位置

### 5.7 全局快捷键

- `⌘K`：命令面板（cmdk）
- 输入框 `Enter`：发送
- 输入框 `Shift+Enter`：换行
- `/mode <name>`：切换 Mode

---

## 6. 状态设计（Loading / Empty / Error）

| 状态 | Chat 区 | 操作演示区 |
|------|---------|-----------|
| Loading | 骨架屏（两行灰色脉冲块） | 名片区 skeleton + 功能区 skeleton |
| Empty | Coco 欢迎消息 + 无会话提示 | default 名片 + 空会话列表 + 快捷操作 |
| Error | "Connection lost" + 重试按钮 | Error icon + 错误信息 |
| Streaming | 打字动画 + 工具调用实时更新 | 功能区「Live Operations」实时更新 |

---

## 7. 数据流

| 数据 | 来源 | 频率 |
|------|------|------|
| 会话列表 | GET /api/chat/sessions | mount |
| 消息历史 | GET /api/chat/history?session_id= | 切换 session 时 |
| 发送消息 | POST /api/chat | 每次发送 |
| 工具调用 | WebSocket (stream) | 实时 |
| 操作可视化事件 | WebSocket (stream) | 实时 |
| ~~操作可视化事件~~ | **待后端新增**：`tool_start`/`tool_delta`/`tool_end` 事件类型 | — |
| Mode 列表 | GET /api/modes | mount |
| 知识库列表 | GET /api/knowledge | 切到 KB 导航时 |
| 场景列表 | GET /api/scenes | 切到 Scenes 导航时 |
| 记忆数据 | GET /api/memory | 切到 Memory 导航时 |
| 系统状态 | GET /api/status | Settings 内 |

---

## 8. 技术方向（非最终选型，spec 留到 plan 阶段定）

- 在现有 `web-ui/` 基础上修改，保留以下基础设施：
  - React + Vite 工程框架
  - 现有 hooks：`useSessionStore`、`useStreaming`、`useSessionStore`
  - 现有 API client 体系
  - `package.json` 依赖（shadcn/ui 组件按需保留或替换）
- 需要替换/重写的部分：
  - `index.css` — 全部 CSS 变量和全局样式重定义
  - `App.tsx` — 路由改为三栏单页
  - `Layout.tsx` — 改三栏骨架
  - 所有 `pages/` — 按新 spec 重写
  - 废弃组件可删除、新组件就地创建
- 字体：Plus Jakarta Sans (Google Fonts)、JetBrains Mono
- 图标：Lucide（已安装）
- 命令面板：cmdk（已安装）

---

## 9. 与旧 spec 的变更清单

| 旧 (2026-05-20) | 新 (v2) |
|-----------------|---------|
| 暖橘色 okch 体系 | 深蓝黑 + 蓝/琥珀 |
| Zen Antique 字体 | Plus Jakarta Sans |
| 白色噪音纹理 | 模糊光晕层 |
| 11 独立页面 + 路由 | 3 栏单页应用，操作演示区切换 |
| Dashboard 为首页 | Chat 为首页 |
| Scene 侧栏 (SceneRail) | 左侧固定导航 |
| Mode 选择器顶栏 | 名片区下拉 + 输入框标签 |
| "安静中带着温度" | "精工暗调 + 暗藏巧思" |
