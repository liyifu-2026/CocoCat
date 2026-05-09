# TUI Block-Style Layout + Command Polish

> **Date:** 2026-05-04
> **Status:** Draft

## 目标

将 TUI 从字符边框（`Borders::ALL`）改为 opencode 风格的背景色块布局，补齐 slash 命令。

## 布局

```
┌──────────── block background ─────────────────────┬──────────┐
│ cococat · leader                                   │ sidebar  │
├────────────────────────────────────┬───────────────┤ (bg色块) │
│  ┃ user message (accent bar+block) │              │ 无边框   │
│  ┃ second line                    │              │          │
│  _Thinking... (grey block)        │              │          │
│  ◈ read_file (inline, no block)   │              │          │
│  ✓ read_file                      │              │          │
│  assistant text (transparent)     │              │          │
│                                    │              │          │
│  ██ input block background █████  │              │          │
│  ▎> type message                   │              │          │
│   leader · gpt-4 · catppuccin    │              │          │
├────────────────────────────────────┴───────────────┤          │
│ status line (thin block)                            │          │
└────────────────────────────────────────────────────┴──────────┘
```

## 改动

### 1. 移除字符框，改用背景色块

| 组件 | 当前 | 改后 |
|------|------|------|
| header | `Borders::ALL` | 无边框，`bg(theme.surface())` + accent 色文字 |
| input_bar | `Borders::ALL` | 无边框，`bg(theme.surface())`，左侧 `▎` accent 色竖条 |
| status_bar | `Borders::ALL` | 无边框，`bg(theme.surface())`，dim 色小字 |
| sidebar | `Borders::ALL` | 无边框，`bg(theme.surface())`，section 标题 accent 色 |
| chat panel | 已无框 | 保持透明背景，无改动 |

每个色块之间留 1 行空白间隔（或直接紧贴，取决于视觉效果）。

### 2. 补齐 slash 命令

| 命令 | 实现 |
|------|------|
| `/clear` | ✅ 已有 |
| `/help` | ✅ 已有 |
| `/model` | 新增：弹出 Dialog 选择模型 |
| `/quit` | ✅ 已有 |
| `/theme` | ✅ 已有 |
| `/session` | 新增：弹出 Session 列表 Dialog |

### 3. 新增 `/model` Dialog

内容同 `/theme` 风格：弹出列表，选中模型。模型列表从 config 读取，暂用默认列表 `["gpt-4", "gpt-3.5-turbo", "claude-3"]`。

### 4. 新增 `/session` Dialog

读 `~/.cococat/sessions/*.jsonl` 文件列表，展示给用户选择，选中后恢复对话（清空当前消息，加载选中 session）。

## 文件变更

- `src/tui/components/header.rs` — 移除 Borders::ALL，加背景色块
- `src/tui/components/input_bar.rs` — 移除 Borders::ALL，加背景色块 + `▎` 竖条
- `src/tui/components/status_bar.rs` — 移除 Borders::ALL，加背景色块
- `src/tui/components/sidebar.rs` — 移除 Borders::ALL，加背景色块
- `src/tui/main.rs` — 添加 `/model` 和 `/session` 命令处理
- `src/tui/app.rs` — 添加 `Dialog::ModelSelector`、`Dialog::SessionSelector`
- `src/tui/components/dialogs.rs` — 添加 model selector、session selector 渲染
