# CocoCat CLI Redesign

> **Date:** 2026-05-04
> **Status:** Approved

## Architecture

```
py-agent/cli/
├── __init__.py       # 模块声明
├── main.py           # Typer app + 子命令注册
├── commands.py       # 所有命令函数 (合并旧文件)
├── config.py         # [新] Config schema (Pydantic) + loader + resolver
├── wizard.py         # [新] 交互式配置向导
├── stream.py         # [新] StreamRenderer + ThinkingSpinner
├── render.py         # [新] 统一输出函数
└── session.py        # [新] 会话持久化
```

## Components

### Config System (`config.py`)
- Pydantic BaseModel: Config → DaemonConfig, ChatConfig, DisplayConfig
- JSON 持久化到 `~/.cococat/config.json`
- `${VAR}` 环境变量解析
- `_load_config()`, `_save_config()`, `_resolve_env_vars()`

### Stream Renderer (`stream.py`)
- `StreamRenderer`: 流式 Markdown 实时渲染
- `ThinkingSpinner`: 思考动画 + pause/resume

### Render Utilities (`render.py`)
- `_print_agent_response()`, `_print_progress()`, `_print_error()`
- 一致的颜色方案: `[green]✓[/green]`, `[red]✗[/red]`, `[cyan]...[/cyan]`

### Interactive Chat (`commands.py`)
- prompt_toolkit 读取输入（历史导航、粘贴支持）
- 流式响应渲染
- 会话持久化到 `~/.cococat/sessions/<session_key>.jsonl`

### Onboard Wizard (`wizard.py`)
- 首次运行引导: LLM key, workspace, default agent
- questionary + prompt_toolkit 交互

## Commands

| Command | Description |
|---------|-------------|
| `cococat onboard` | 首次配置向导 |
| `cococat config show` | 显示当前配置 |
| `cococat config set <key> <value>` | 快捷修改配置 |
| `cococat chat` | 交互式聊天 |
| `cococat chat send <agent> <message>` | 单次消息 |
| `cococat agent list` | 列出 Agent |
| `cococat agent status <id>` | Agent 详情 |
| `cococat daemon start/stop/status` | 控制守护进程 |
| `cococat status` | 系统总览 |

## Files to Delete
- `py-agent/cli/agents.py`
- `py-agent/cli/chat.py`
- `py-agent/cli/daemon.py`
- `py-agent/cli/mailbox.py`
- `py-agent/cli/hire.py`
- `py-agent/cli/status.py`
