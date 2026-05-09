# TUI Layout Alignment — opencode 风格 UI

> **Date:** 2026-05-04
> **Status:** Draft

## 目标

将 CocoCat TUI 布局与 opencode 参考实现对齐：右侧固定宽度 sidebar、scrollbar、增强 input bar。

## 布局架构

```
┌──────────────────────────────────────────────────────────┐
│ Header: coco cat                                 主题名  │
├────────────────────────────────┬─────────────────────────┤
│  Chat Panel (flexGrow=1)       │ Sidebar (42列, 可折叠)  │
│  ┌─────────────────────────┐   │ ┌─ Team ────────────┐  │
│  │ Messages in scrollbox   │   │ │ leader    ● run   │  │
│  │ - 用户消息               │   │ │ emp_a     ● run   │  │
│  │ - Assistant: delta      │   │ │ emp_b     ○ idle  │  │
│  │ - Assistant: reasoning  │   │ └──────────────────┘  │
│  │ - Assistant: tool start │   │ ┌─ Session ─────────┐ │
│  │ - Assistant: text       │   │ │ Messages  12      │ │
│  │   ░░░ scrollbar ░░░░    │   │ │ Tokens    4.2K    │ │
│  └─────────────────────────┘   │ └──────────────────┘  │
│  ┌─ Message ───────────────┐   │ ┌─ Tools ───────────┐ │
│  │ > Type a message...      │   │ │ read_file  ✓ 3   │ │
│  │ leader · model · theme·t │   │ │ search     ✓ 2   │ │
│  └──────────────────────────┘   │ └──────────────────┘  │
│                                 │ ┌─ Mail ────────────┐ │
│                                 │ │ 2 unread          │ │
│                                 │ │ 1 dispatch pending│ │
│                                 │ └──────────────────┘  │
│  Status: leader | default |    │ CocoCat v0.1.0        │
│  catppuccin-mocha               │ catppuccin-mocha      │
├────────────────────────────────┴─────────────────────────┤
└──────────────────────────────────────────────────────────┘
```

**关键原则：**
- Sidebar 在右侧，固定 42 列宽
- 终端 >120 列自动显示，≤120 列自动隐藏（可用 Ctrl+B 切换）
- 窄终端时 sidebar 以浮层覆盖形式出现
- Chat Panel 占满剩余空间

## Components

### 1. Sidebar（右侧，42列）

4 个可折叠区块 + 底部信息：

| 区块 | 内容 | 数据源 |
|------|------|--------|
| Team | agent 列表 + 状态（● running/○ idle/✗ error） | PID 文件检测 + daemon |
| Session | 消息数、token 用量（当前/上限）、当前 agent | App state |
| Tools | 本次会话工具调用统计（完成次数/进行中） | TuiEvent 累积统计 |
| Mail | 未读邮件数、待处理 dispatch 数 | 文件系统 (`~/.cococat/agents/mailbox/`) |

每个区块可折叠展开（点击标题行）。

### 2. Scrollbar（Chat Panel 右侧）

- 使用 ratatui `Scrollbar` widget
- `stickyScroll` 模式：新消息自动跟随底部
- 用户上滚（↑/PageUp/鼠标滚轮）时取消粘性
- 上滚后底部显示 `↓ 最新消息` 提示条
- 滚动加速：PageUp/Down 翻半屏，↑↓ 翻一行

### 3. Input Bar（增强）

```
┌─ Message ───────────────────────────────────────────────┐
│ > Type a message...                                      │
│ leader · gpt-4 · catppuccin · 4.2K tok                  │
└──────────────────────────────────────────────────────────┘
```

- 元数据行：agent · model · theme · token
- agent 名称前有彩色竖条，颜色随 agent 变化
- 历史导航 ↑↓、自动补全 @ 和 /

### 4. Header 改造

移除原有 Header widget，改用自定义：
- 左侧：cococat 名称 + 当前 agent 名
- 右侧：当前主题名

### 5. 布局/快捷键变动

| 按键 | 功能 |
|------|------|
| `Ctrl+B` | 切换 sidebar 显示 |
| `Ctrl+Q` | 退出 |
| `Tab` | 切换到输入框 |
| `↑↓` | 历史导航（输入模式）/ 滚动（普通模式） |
| `PageUp/PageDown` | 翻半屏 |
| `Esc` | 关闭 sidebar 浮层 / 关闭 dialog |

团队区块设计为可点击选中 agent，切换聊天对象。选中后输入栏的 agent 名会变化。

## 文件变更清单

### 修改
- `src/tui/main.rs` — 布局改为右 sidebar + scrollbar + 新 input bar
- `src/tui/app.rs` — 新增 sidebar 区块状态、tool 统计、mail/dispatch 计数
- `src/tui/components/sidebar.rs` — 重写：4 个折叠区块 + agent 状态 + 统计信息
- `src/tui/components/chat_panel.rs` — 集成 scrollbar
- `src/tui/components/input_bar.rs` — 增加元数据行
- `src/tui/theme/theme.rs` — 新增 sidebar/scrollbar 相关颜色

### 新增
- `src/tui/components/header.rs` — 自定义 header
- `src/tui/types/stats.rs` — ToolStats、SessionStats 等统计类型

## 实施路径

1. **Phase 1** — 布局重排：sidebar 改右侧 + header 改造 + 固定 42 列
2. **Phase 2** — Scrollbar 集成 + sticky scroll 逻辑
3. **Phase 3** — Sidebar 区块（Team/Session/Tools/Mail）填充数据
4. **Phase 4** — Input Bar 元数据行 + 布局细节打磨
