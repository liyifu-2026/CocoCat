# CLI v2 Implementation Plan

**Goal:** Rewrite CocoCat CLI with nanobot-inspired architecture - Config, stream rendering, interactive chat, onboard wizard.

**Architecture:** Thin CLI layer + Pydantic Config + StreamRenderer + prompt_toolkit REPL.

**Tech Stack:** Python 3.10+, typer, rich, pydantic, prompt_toolkit, questionary

---

### File Changes
- Create: `py-agent/cli/config.py` - Pydantic Config schema + loader/resolver
- Create: `py-agent/cli/stream.py` - StreamRenderer + ThinkingSpinner
- Create: `py-agent/cli/render.py` - Unified output functions
- Create: `py-agent/cli/session.py` - Session persistence
- Create: `py-agent/cli/wizard.py` - Interactive setup wizard
- Rewrite: `py-agent/cli/commands.py` - All commands merged into one file
- Modify: `py-agent/cli/main.py` - Register commands
- Delete: `py-agent/cli/agents.py`, `chat.py`, `daemon.py`, `mailbox.py`, `hire.py`, `status.py`

## Task 1: Config system

Create `py-agent/cli/config.py`:

```python
from pydantic import BaseModel
import json, os, re
from pathlib import Path

CONFIG_DIR = Path.home() / ".cococat"
CONFIG_PATH = CONFIG_DIR / "config.json"


class DaemonConfig(BaseModel):
    cargo_path: str = str(Path.home() / ".cargo" / "bin" / "cargo")
    health_check_interval: int = 15
    agent_startup_timeout: int = 45


class ChatConfig(BaseModel):
    default_agent: str = "leader"
    response_timeout: int = 120
    session_persistence: bool = True


class DisplayConfig(BaseModel):
    render_markdown: bool = True
    show_progress: bool = True


class Config(BaseModel):
    workspace: str = str(Path.home() / ".cococat" / "workspace")
    daemon: DaemonConfig = DaemonConfig()
    chat: ChatConfig = ChatConfig()
    display: DisplayConfig = DisplayConfig()


def _resolve_env_vars(obj):
    """Replace ${VAR} patterns with environment variable values."""
    if isinstance(obj, str):
        def replacer(m):
            var = m.group(1)
            return os.environ.get(var, m.group(0))
        return re.sub(r'\$\{(\w+)\}', replacer, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars(v) for v in obj]
    return obj


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    try:
        raw = json.loads(CONFIG_PATH.read_text())
        resolved = _resolve_env_vars(raw)
        return Config.model_validate(resolved)
    except Exception:
        return Config()


def save_config(config: Config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
```

## Task 2: Stream renderer

Create `py-agent/cli/stream.py` with StreamRenderer and ThinkingSpinner.

## Task 3: Render utilities

Create `py-agent/cli/render.py` with _print_agent_response, _print_progress, _print_error.

## Task 4: Session persistence

Create `py-agent/cli/session.py` with Session class for chat history persistence.

## Task 5: Commands

Rewrite `py-agent/cli/commands.py` merging all old files into one file with all commands.

## Task 6: Wizard

Create `py-agent/cli/wizard.py` with interactive setup wizard using questionary.

## Task 7: Main entry point

Update `py-agent/cli/main.py` to register all commands and cleanup old files.

## Task 8: Delete old files

Remove agents.py, chat.py, daemon.py, mailbox.py, hire.py, status.py.
