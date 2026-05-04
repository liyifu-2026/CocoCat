"""CocoCat CLI configuration — Pydantic schema + persistence + migration."""
from pydantic import BaseModel
import json
import os
import re
from pathlib import Path

CONFIG_DIR = Path.home() / ".cococat"
CONFIG_PATH = CONFIG_DIR / "config.json"

_CONFIG_MIGRATIONS = []


def _register_migration(version_tag: str, fn):
    """Register a config migration function."""
    _CONFIG_MIGRATIONS.append((version_tag, fn))


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
    config_version: str = "1"
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


def _merge_missing_defaults(existing: dict, defaults: dict) -> dict:
    """Recursively fill missing keys from defaults without overwriting user values."""
    merged = dict(existing)
    for key, value in defaults.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_missing_defaults(merged[key], value)
    return merged


def _migrate_config(raw: dict) -> dict:
    """Run registered migrations in order (nanobot _migrate_config pattern)."""
    for version_tag, fn in _CONFIG_MIGRATIONS:
        if raw.get("config_version", "0") < version_tag:
            try:
                fn(raw)
                raw["config_version"] = version_tag
            except Exception:
                break
    return raw


def _warn_deprecated(raw: dict):
    """Print warnings for deprecated config keys."""
    deprecated = {
        "memoryWindow": "`memoryWindow` is no longer used and can be safely removed.",
    }
    for key, msg in deprecated.items():
        if key in raw:
            import warnings
            warnings.warn(f"Config: {msg}")


def load_config(config_path: str | None = None) -> Config:
    """Load config, run migrations, return Config."""
    path = Path(config_path).expanduser().resolve() if config_path else CONFIG_PATH

    if not path.exists():
        return Config()

    try:
        raw = json.loads(path.read_text())
        raw = _migrate_config(raw)
        _warn_deprecated(raw)
        resolved = _resolve_env_vars(raw)
        return Config.model_validate(resolved)
    except Exception:
        return Config()


def save_config(config: Config):
    """Persist config to JSON."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
