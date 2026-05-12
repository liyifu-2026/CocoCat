# TUI Interaction Polish — opencode 对齐

> **Date:** 2026-05-04
> **Status:** Draft

## 目标

对齐 opencode TUI 的交互体验：聊天视觉、slash 补全、sidebar 点击交互。

## 1. 聊天视觉 + 流式布局

### 消息渲染

移除 `Borders::ALL` 全框，改为 opencode 最小化风格：

| 消息类型 | 样式 |
|---------|------|
| 用户消息 | 左侧竖线 `┃` + agent 色，时间戳，内容 |
| Assistant delta | 无边框，仅缩进 |
| Reasoning | 左侧淡灰竖线 + 灰色斜体 `_Thinking..._` |
| Tool start | inline `◈ tool_name` |
| Tool done | inline `✓ tool_name` |
| 消息间隔 | 空行 |

### 消息尾部元数据

每段 assistant 消息结束后显示：
```
▣ Build · gpt-4 · 2.3s
```

## 2. Slash 命令自动补全

输入 `/` 且光标在位置 0 时弹出浮动列表：

- 选项：`/clear`, `/help`, `/model`, `/quit`, `/theme`, `/session`
- `↑↓` 导航，`Enter` 选中，`Esc` 关闭
- 继续打字过滤
- 渲染在 input_bar 上方，`Clear` widget 覆盖

## 3. Sidebar 交互

### 折叠展开
| 区块 | 点击标题 | 点击内容 |
|------|---------|---------|
| Team | 折叠/展开 | 点击 agent → 切换聊天目标 |
| Session | 折叠/展开 | 只读 |
| Tools | 折叠/展开 | 只读 |
| Mail | 折叠/展开 | 点击 mail → 回复 dialog；点击 dispatch → 处理 dialog |

### Mail 回复 Dialog

```
┌─ Reply to leader ────────────────────┐
│                                       │
│  来信内容 (最多 20 行)                │
│                                       │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│                                       │
│ > 输入回复...                         │
│                                       │
│  [Send]                               │
└───────────────────────────────────────┘
```

- 来信显示纯文本，最多 20 行截断
- 分割线
- 输入框 `>` 前缀
- Enter 发送（写入 `agents/mailbox/<agent>/inbox.jsonl`）
- Esc 关闭

### Dispatch Dialog

```
┌─ Dispatch ───────────────────────────┐
│ Task: 分析日志文件                     │
│ From: leader                          │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│ > 开始处理                            │
│                                       │
│  [Accept]  [Reject]                   │
└───────────────────────────────────────┘
```

### 视觉反馈
- 鼠标悬停行时背景色变化
- 当前对话 agent 高亮（`▶` 标记）
- 需要启用 `EnableMouseCapture` 处理 `Event::Mouse`

## 文件变更

### 修改
- `src/tui/components/chat_panel.rs` — 重写消息渲染（无框、竖线、元数据脚注）
- `src/tui/components/sidebar.rs` — 点击处理、mail/dispatch dialog 布局
- `src/tui/main.rs` — EnableMouseCapture、Event::Mouse 处理、autocomplete 状态
- `src/tui/components/input_bar.rs` — 适配新消息样式

### 新增
- `src/tui/components/autocomplete.rs` — slash 命令补全浮动列表
- `src/tui/components/reply_dialog.rs` — mail 回复 dialog + dispatch dialog
