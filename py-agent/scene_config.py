"""Scene configuration loader — reads scenes/{scene_id}/ config files."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChannelConfig:
    channel_type: str = ""
    enabled: bool = True
    config: dict = field(default_factory=dict)


@dataclass
class SceneConfig:
    scene_id: str = ""
    name: str = ""
    context: str = ""
    agent_id: Optional[str] = None
    mounted_kbs: list[str] = field(default_factory=list)
    env_skills: list[str] = field(default_factory=list)
    channels: list[ChannelConfig] = field(default_factory=list)
    display: dict = field(default_factory=dict)


def _scenes_dir() -> str:
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scenes")
    )


def load_scene_config(scene_id: str) -> Optional[SceneConfig]:
    """Load and return SceneConfig from scenes/{scene_id}/ directory.

    Returns None if scene directory doesn't exist.
    """
    scene_dir = os.path.join(_scenes_dir(), scene_id)
    if not os.path.isdir(scene_dir):
        return None

    config = SceneConfig(scene_id=scene_id)

    # Load CONTEXT.md
    context_path = os.path.join(scene_dir, "CONTEXT.md")
    if os.path.exists(context_path):
        with open(context_path, "r", encoding="utf-8") as f:
            config.context = f.read()
        first_line = config.context.strip().split("\n")[0].strip()
        if first_line.startswith("# "):
            config.name = first_line[2:].strip()
        else:
            config.name = scene_id
    else:
        config.name = scene_id

    # Load mounted_kbs.json
    kb_path = os.path.join(scene_dir, "mounted_kbs.json")
    if os.path.exists(kb_path):
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                config.mounted_kbs = data.get("mounted", [])
        except Exception:
            pass

    # Load skills/manifest.json
    manifest_path = os.path.join(scene_dir, "skills", "manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                config.env_skills = data.get("env_skills", [])
        except Exception:
            pass

    # Load entries.json
    entries_path = os.path.join(scene_dir, "entries.json")
    if os.path.exists(entries_path):
        try:
            with open(entries_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("entries", []):
                    cfg = ChannelConfig(
                        channel_type=entry.get("channel", ""),
                        enabled=entry.get("enabled", True),
                        config=entry.get("config", {}),
                    )
                    config.channels.append(cfg)
        except Exception:
            pass

    # Load display.json
    display_path = os.path.join(scene_dir, "display.json")
    if os.path.exists(display_path):
        try:
            with open(display_path, "r", encoding="utf-8") as f:
                config.display = json.load(f)
        except Exception:
            pass

    return config


def list_scenes() -> list[str]:
    """Return all scene IDs (directory names under scenes/)."""
    sdir = _scenes_dir()
    if not os.path.isdir(sdir):
        return []
    return sorted(
        d for d in os.listdir(sdir)
        if os.path.isdir(os.path.join(sdir, d)) and not d.startswith("_")
    )
