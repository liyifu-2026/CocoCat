"""Scene config — loads scene.yaml from filesystem."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

import yaml

logger = logging.getLogger("cococat.scene")


@dataclass
class SceneConfig:
    """Scene configuration loaded from scene.yaml."""
    id: str
    name: str = ""
    context: str = ""
    kbs: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    channels: list[dict] = field(default_factory=list)


def load_scene_config(
    scene_id: str,
    scenes_dir: str = "scenes",
) -> Optional[SceneConfig]:
    """Load scene configuration from scenes/{scene_id}/scene.yaml."""
    path = os.path.join(scenes_dir, scene_id, "scene.yaml")
    if not os.path.exists(path):
        return None

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        logger.warning("Failed to load scene config %s: %s", path, e)
        return None

    if not isinstance(data, dict) or "id" not in data:
        logger.warning("Invalid scene config at %s", path)
        return None

    return SceneConfig(
        id=data.get("id", scene_id),
        name=data.get("name", scene_id),
        context=data.get("context", ""),
        kbs=data.get("kbs", []),
        skills=data.get("skills", []),
        channels=data.get("channels", []),
    )


def list_scenes(scenes_dir: str = "scenes") -> list[SceneConfig]:
    """List all scenes in the scenes directory."""
    if not os.path.isdir(scenes_dir):
        return []

    results = []
    for name in os.listdir(scenes_dir):
        config = load_scene_config(name, scenes_dir)
        if config:
            results.append(config)

    return results
