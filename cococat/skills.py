"""Skills loader — reads .md skill files and creates executable tools."""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger("cococat.skills")

# YAML frontmatter pattern
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_skill_file(path: str) -> Optional[dict]:
    """Load a skill .md file and return a tool definition.

    Skill files can have optional YAML frontmatter with name/description.
    If no frontmatter, the filename (minus .md) becomes the name.
    """
    if not os.path.exists(path):
        return None

    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None

    # Extract frontmatter
    name = os.path.splitext(os.path.basename(path))[0]
    description = raw[:200]
    params = {}

    match = _FRONTMATTER_RE.match(raw)
    if match:
        try:
            import yaml
            fm = yaml.safe_load(match.group(1))
            if isinstance(fm, dict):
                name = fm.get("name", name)
                description = fm.get("description", description)
                params = fm.get("parameters", {})
        except Exception:
            pass  # Use defaults
        body = raw[match.end():]
    else:
        body = raw

    return {
        "name": name,
        "description": description[:500],
        "parameters": params,
        "body": body,
    }


def load_scene_skills(scene_id: str, skills_dir: str = "skills") -> list[dict]:
    """Load all skills for a scene from skills/scenes/{scene_id}/ directory."""
    scene_skills_dir = os.path.join(skills_dir, "scenes", scene_id)
    if not os.path.isdir(scene_skills_dir):
        return []

    tools = []
    for fname in sorted(os.listdir(scene_skills_dir)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(scene_skills_dir, fname)
        skill = load_skill_file(path)
        if skill:
            skill["execute"] = lambda p, ctx, body=skill["body"]: f"[Skill] {body[:1000]}"
            tools.append(skill)

    return tools


def load_global_skills(skills_dir: str = "skills") -> list[dict]:
    """Load all global skills from skills/public/ directory."""
    public_dir = os.path.join(skills_dir, "public")
    if not os.path.isdir(public_dir):
        return []

    tools = []
    for fname in sorted(os.listdir(public_dir)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(public_dir, fname)
        skill = load_skill_file(path)
        if skill:
            skill["execute"] = lambda p, ctx, body=skill["body"]: f"[Skill] {body[:1000]}"
            tools.append(skill)

    return tools
