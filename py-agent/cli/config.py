"""CocoCat CLI configuration — Pydantic schema + JSON persistence."""
from pydantic import BaseModel
import json
import os
import re
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
    """Replace ${VAR_NAME} with environment variable values recursively."""
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
    """Load config from ~/.cococat/config.json, or return defaults."""
    if not CONFIG_PATH.exists():
        return Config()
    try:
        raw = json.loads(CONFIG_PATH.read_text())
        resolved = _resolve_env_vars(raw)
        return Config.model_validate(resolved)
    except Exception:
        return Config()


def save_config(config: Config):
    """Persist config to ~/.cococat/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
