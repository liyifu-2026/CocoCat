"""Centralized config access — single seam for all config file I/O.

All file reads flow through here. Callers get typed data without knowing which
file or format backs it. In-memory override supported for testing.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("cococat.config_store")


class ConfigStore:
    """Single source of truth for application configuration.

    Caches reads in memory. Paths are injectable for test isolation.
    """

    def __init__(
        self,
        config_dir: str = "config",
        env_path: str = ".env",
        user_id: str | None = None,
    ):
        self._user_id = user_id
        if user_id:
            config_dir = f"config/users/{user_id}"
        self._config_dir = Path(config_dir)
        self._env_path = Path(env_path)

        self._auth_cache: dict[str, str] | None = None
        self._defaults_cache: dict | None = None
        self._models_cache: dict | None = None
        self._providers_cache: list[dict] | None = None
        self._channels_cache: dict | None = None
        self._env_cache: dict[str, str] | None = None
        self._coco_prompt_cache: str | None | _MISSING = _MISSING
        self._residents_cache: dict[str, dict] | None = None

    # ── paths ────────────────────────────────────────────────

    @property
    def auth_path(self) -> Path:
        override = os.environ.get("COCOCAT_AUTH_FILE")
        return Path(override) if override else self._config_dir / "auth.json"

    @property
    def defaults_path(self) -> Path:
        return self._config_dir / "defaults.json"

    @property
    def models_path(self) -> Path:
        override = os.environ.get("COCOCAT_MODELS_FILE")
        return Path(override) if override else self._config_dir / "models.json"

    @property
    def providers_path(self) -> Path:
        override = os.environ.get("COCOCAT_CUSTOM_PROVIDERS_FILE")
        return Path(override) if override else self._config_dir / "providers.json"

    @property
    def main_yaml_path(self) -> Path:
        return self._config_dir / "main.yaml"

    @property
    def residents_dir(self) -> Path:
        return self._config_dir / "residents"

    @property
    def prompts_dir(self) -> Path:
        return self._config_dir / "prompts"

    # ── data directories ──────────────────────────────────────

    @property
    def agents_dir(self) -> Path:
        override = os.environ.get("COCOCAT_AGENTS_DIR")
        return Path(override) if override else Path("agents")

    @property
    def knowledge_dir(self) -> Path:
        override = os.environ.get("COCOCAT_KNOWLEDGE_DIR")
        return Path(override) if override else Path("knowledge")

    @property
    def runs_dir(self) -> Path:
        override = os.environ.get("COCOCAT_RUNS_DIR")
        return Path(override) if override else Path("runs")

    @property
    def cron_dir(self) -> Path:
        return self.runs_dir / "cron"

    @property
    def memory_dir(self) -> Path:
        override = os.environ.get("COCOCAT_MEMORY_DIR")
        return Path(override) if override else Path("memory")

    @property
    def scenes_dir(self) -> Path:
        override = os.environ.get("COCOCAT_SCENES_DIR")
        return Path(override) if override else Path("scenes")

    @property
    def skills_dir(self) -> Path:
        override = os.environ.get("COCOCAT_SKILLS_DIR")
        return Path(override) if override else Path("skills")

    # ── helper ───────────────────────────────────────────────

    @staticmethod
    def _read_json(path: Path) -> dict | list | None:
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read %s", path)
            return None

    @staticmethod
    def _write_json(path: Path, data: dict | list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def _read_yaml(path: Path) -> dict | list | None:
        if not path.is_file():
            return None
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            logger.warning("Failed to read %s", path)
            return None

    # ── env ──────────────────────────────────────────────────

    def _env_file_path(self) -> Path:
        override = os.environ.get("COCOCAT_ENV_FILE")
        return Path(override) if override else self._env_path

    def _load_env(self) -> dict[str, str]:
        env_path = self._env_file_path()
        pairs: dict[str, str] = {}
        if not env_path.is_file():
            return pairs
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                pairs[k.strip()] = v.strip().strip('"').strip("'")
        return pairs

    def get_env(self, key: str, default: str | None = None) -> str | None:
        return os.environ.get(key, default)

    def set_env(self, key: str, value: str) -> None:
        os.environ[key] = value
        self._env_cache = None  # invalidate
        env_path = self._env_file_path()
        if env_path.is_file():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        else:
            lines = []
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}=") or line.strip().startswith(f"# {key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def env_keys(self) -> dict[str, str]:
        if self._env_cache is None:
            self._env_cache = self._load_env()
        return {**self._env_cache, **{k: v for k, v in os.environ.items() if k.startswith("COCOCAT_")}}

    # ── auth ─────────────────────────────────────────────────

    def get_auth(self, provider: str) -> str | None:
        if self._auth_cache is None:
            data = self._read_json(self.auth_path)
            self._auth_cache = data if isinstance(data, dict) else {}
        return self._auth_cache.get(provider)

    def set_auth(self, provider: str, key: str) -> None:
        data = self._read_json(self.auth_path)
        if not isinstance(data, dict):
            data = {}
        data[provider] = key
        self._write_json(self.auth_path, data)
        self._auth_cache = data

    def all_auth(self) -> dict[str, str]:
        if self._auth_cache is None:
            data = self._read_json(self.auth_path)
            self._auth_cache = data if isinstance(data, dict) else {}
        return dict(self._auth_cache)

    # ── defaults ─────────────────────────────────────────────

    def get_default(self, key: str | None = None) -> Any:
        if self._defaults_cache is None:
            data = self._read_json(self.defaults_path)
            self._defaults_cache = data if isinstance(data, dict) else {}
        if key is None:
            return dict(self._defaults_cache)
        return self._defaults_cache.get(key)

    def save_defaults(self, data: dict) -> None:
        self._write_json(self.defaults_path, data)
        self._defaults_cache = data

    # ── channels (main.yaml) ─────────────────────────────────

    def get_channel_configs(self) -> dict:
        if self._channels_cache is None:
            data = self._read_yaml(self.main_yaml_path)
            self._channels_cache = data if isinstance(data, dict) else {}
        return dict(self._channels_cache)

    def save_channel_configs(self, data: dict) -> None:
        self.main_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        self.main_yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        self._channels_cache = data

    # ── models ───────────────────────────────────────────────

    def get_models(self) -> dict:
        if self._models_cache is None:
            data = self._read_json(self.models_path)
            self._models_cache = data if isinstance(data, dict) else {}
        return dict(self._models_cache)

    def save_models(self, data: dict) -> None:
        self._write_json(self.models_path, data)
        self._models_cache = data

    def get_custom_providers(self) -> list[dict]:
        if self._providers_cache is None:
            data = self._read_json(self.providers_path)
            self._providers_cache = data if isinstance(data, list) else []
        return list(self._providers_cache)

    def save_custom_providers(self, data: list[dict]) -> None:
        self._write_json(self.providers_path, data)
        self._providers_cache = data

    # ── prompt ───────────────────────────────────────────────

    def get_coco_prompt(self) -> str | None:
        if self._coco_prompt_cache is _MISSING:
            path = self.prompts_dir / "coco.txt"
            if not path.is_file():
                self._coco_prompt_cache = None
            else:
                try:
                    self._coco_prompt_cache = path.read_text(encoding="utf-8").strip() or None
                except OSError:
                    self._coco_prompt_cache = None
        return self._coco_prompt_cache

    def save_coco_prompt(self, text: str) -> None:
        path = self.prompts_dir / "coco.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._coco_prompt_cache = text

    def delete_coco_prompt(self) -> bool:
        path = self.prompts_dir / "coco.txt"
        if path.is_file():
            path.unlink()
            self._coco_prompt_cache = None
            return True
        self._coco_prompt_cache = None
        return False

    # ── residents ────────────────────────────────────────────

    def get_resident_configs(self) -> dict[str, dict]:
        if self._residents_cache is None:
            configs: dict[str, dict] = {}
            dir_ = self.residents_dir
            if dir_.is_dir():
                for f in sorted(dir_.iterdir()):
                    if f.suffix.lower() in (".yaml", ".yml"):
                        try:
                            data = yaml.safe_load(f.read_text(encoding="utf-8"))
                            if isinstance(data, dict) and "id" in data:
                                configs[data["id"]] = data
                        except (yaml.YAMLError, OSError):
                            logger.warning("Failed to load resident config: %s", f)
            self._residents_cache = configs
        return dict(self._residents_cache)

    def save_resident_config(self, agent_id: str, config: dict) -> None:
        self.residents_dir.mkdir(parents=True, exist_ok=True)
        path = self.residents_dir / f"{agent_id}.yaml"
        path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        self._residents_cache = None  # invalidate

    def invalidate(self) -> None:
        """Clear all caches. Useful after config file changes outside this store."""
        self._auth_cache = None
        self._defaults_cache = None
        self._models_cache = None
        self._providers_cache = None
        self._channels_cache = None
        self._env_cache = None
        self._coco_prompt_cache = _MISSING
        self._residents_cache = None


class _Missing:
    pass


_MISSING = _Missing()
