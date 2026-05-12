# CocoCat TUI/UX Redesign — opencode 级别体验

> **Date:** 2026-05-04
> **Status:** Draft

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 cococat-tui (Rust)                    │
│              ratatui 0.19+, syntect                  │
│                                                      │
│  ┌──────────┐  ┌──────────────────┐  ┌───────────┐ │
│  │ Sidebar   │  │  Chat Panel      │  │ Status    │ │
│  │ (30% v)   │  │  (70% v)         │  │ Bar (1ln) │ │
│  │ - Sessions│  │  - Markdown 渲染  │  │ - agent   │ │
│  │ - Themes  │  │  - 推理过程可视化 │  │ - model   │ │
│  │ - Help    │  │  - 工具调用可视化 │  │ - mode    │ │
│  └──────────┘  │  - 代码语法高亮   │  └───────────┘
│                 └──────────────────┘                 │
│                 ┌──────────────────┐                 │
│                 │  Input Bar       │                 │
│                 │  (历史/补全/状态) │                 │
│                 └──────────────────┘                 │
└──────────────────────┬──────────────────────────────┘
                       │ JSON-RPC (子进程 stdin/stdout)
                       ▼
┌─────────────────────────────────────────────────────┐
│              agent_runtime.py (Python)                │
│              ReAct loop, task_stream 协议            │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│              cococat CLI (Python/Typer)               │
│              管理命令：config, daemon, agent,          │
│              theme, doctor, upgrade                   │
└─────────────────────────────────────────────────────┘
```

**原则：** Rust TUI 是交互式唯一的入口。Python CLI 只做非交互管理命令。两者共享 `~/.cococat/` 下的配置和会话数据。

## Components

### 1. Chat Panel (`chat_panel.rs`)

每条消息渲染为多个垂直排列的事件块：

- **`delta` 事件** → `Paragraph` 用 `comrak`/`pulldown-cmark` 转 ratatui `Span`，`syntect` 代码高亮
- **`reasoning` 事件** → `Paragraph` 用 `Style::new().dim().italic()`
- **`tool_start`/`tool_done`/`tool_error`** → `List`，每行一个 tool，颜色随状态变化（蓝→绿/红）
- 长对话用 `Scrollbar`，自动跟随最新消息

**流式更新：**
- 子线程：`mpsc::channel` 发送 `TuiEvent` 枚举
- 主线程：每次渲染 tick 消费所有待处理事件，渐进式追加到当前消息
- 渲染频率固定 30fps

**依赖：** `comrak` (Markdown 解析), `syntect` (代码高亮), `ratatui`

### 2. Input Bar (`input_bar.rs`)

- `tui-textarea` crate 或自定义 `Editor` widget
- 历史导航：↑↓ 遍历 `VecDeque`，退出时 flush 到 `~/.cococat/history/<agent>.txt`
- 自动补全：`@` 触发 agent 列表、`/` 触发命令（`/clear`, `/help`, `/theme`, `/model`, `/session`）
- 右侧状态：`[Tab: leader] [model: gpt-4]`

### 3. Sidebar (`sidebar.rs`)

可折叠（`Ctrl+B`），水平分割 30%/70%，Tab 切换：

| Tab | 内容 |
|-----|------|
| Sessions | 会话列表，新建/重命名/删除，当前高亮，`Ctrl+P` fuzzy find |
| Context | tokens 用量、当前工具上下文 |
| Help | 快捷键一览、版本信息 |

### 4. Theme System (`theme.rs`)

JSON 文件定义在 `~/.cococat/themes/*.json`，结构：

```json
{
  "name": "catppuccin-mocha",
  "colors": {
    "background": "#1e1e2e", "surface": "#313244",
    "text": "#cdd6f4", "accent": "#89b4fa",
    "success": "#a6e3a1", "error": "#f38ba8",
    "warning": "#fab387", "thinking": "#6c7086",
    "tool": "#89b4fa", "code_bg": "#181825"
  }
}
```

内置 10+ 主题，运行时 `/theme <name>` 切换，与 `ratatui::Style` 直接映射。

### 5. Dialog System

弹出式模态窗口：

| 触发 | 弹窗意图 |
|------|---------|
| `/theme` | 主题选择列表 + 实时预览 |
| `/model` | 模型选择（从 config 读取） |
| `Ctrl+P` | 快速 session 切换（fuzzy find） |
| `/?` | 帮助/快捷键一览 |

### 6. Python CLI 改进

| 命令 | 改进 |
|------|------|
| `cococat tui` | 改为 exec Rust 二进制 |
| `cococat theme list` / `theme set` | 新增，管理主题 |
| `cococat doctor` | 新增，诊断环境 |
| `cococat upgrade` | 新增，自更新 |
| 所有命令 | 输出风格统一，`--json` 支持，颜色与 TUI theme 对齐 |

### Key Dependencies (Rust)

| Crate | 用途 |
|-------|------|
| `ratatui` | TUI 框架 |
| `tui-textarea` | 输入编辑 |
| `comrak` | Markdown → AST → ratatui |
| `syntect` | 代码语法高亮 |
| `serde_json` | JSON-RPC / config |
| `serde` | 序列化 |
| `chrono` | 时间戳 |
| `dirs` | `~/.cococat` 路径 |
| `mpsc` | 线程间事件 |

## 文件变更清单

### 新增（Rust）
```
src/tui/
├── main.rs
├── app.rs
├── components/
│   ├── chat_panel.rs
│   ├── input_bar.rs
│   ├── sidebar.rs
│   ├── status_bar.rs
│   └── dialogs/
│       ├── mod.rs
│       ├── theme_selector.rs
│       ├── model_selector.rs
│       ├── session_switcher.rs
│       └── help.rs
├── protocol/
│   ├── mod.rs
│   └── client.rs
├── session/
│   ├── mod.rs
│   └── manager.rs
├── config/
│   ├── mod.rs
│   └── config.rs
└── theme/
    ├── mod.rs
    └── theme.rs
```

### 修改（Python）
- `py-agent/cli/commands.py` — 添加 theme/doctor/upgrade 命令，改进输出风格
- `py-agent/cli/main.py` — 注册新命令
- `py-agent/cli/render.py` — 颜色与 TUI 主题对齐
- `py-agent/cli/tui/app.py` — 此文件将被 Rust TUI 替代，或保留作为 fallback

### 修改（Rust）
- `Cargo.toml` — 新增依赖
- `src/main.rs` — 可选：添加 `--tui` 标志或 standalone 模式

## 实施路径

1. **Phase 1 — 基础设施**：Rust 项目脚手架 + config 加载 + JSON-RPC 协议客户端 + 基本事件循环
2. **Phase 2 — Chat Panel**：对话区 Markdown 渲染 + 流式事件消费 + 消息历史
3. **Phase 3 — Input Bar**：文本编辑 + 历史导航 + 自动补全
4. **Phase 4 — Sidebar + Dialogs**：会话管理 + 主题切换 + 帮助
5. **Phase 5 — Python CLI 对齐**：theme/doctor/upgrade 命令 + 输出风格统一
6. **Phase 6 — Polish**：内置主题包 + 动画 + 性能优化 + 错误处理
