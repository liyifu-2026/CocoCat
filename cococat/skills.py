"""Skills loader — reads .md skill files from skills/ directory."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger("cococat.skills")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

MAX_PROMPT_PER_SKILL = 4000
MAX_TOOL_OUTPUT = 2000


def load_skill(name: str, skills_dir: str = "skills") -> dict[str, Any] | None:
    """Load a single skill from skills/{name}.md.

    Returns dict with keys: id, name, description, tags, as_tool, body.
    Returns None if file not found or unreadable.
    """
    path = os.path.join(skills_dir, f"{name}.md")
    if not os.path.exists(path):
        return None

    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None

    display_name = name
    description = raw[:200].strip()
    tags: list[str] = []
    as_tool = False

    match = _FRONTMATTER_RE.match(raw)
    if match:
        try:
            import yaml
            fm = yaml.safe_load(match.group(1))
            if isinstance(fm, dict):
                display_name = fm.get("name", display_name)
                description = fm.get("description", description)
                tags = fm.get("tags") or []
                as_tool = bool(fm.get("as_tool", False))
        except Exception:
            pass
        body = raw[match.end():].strip()
    else:
        body = raw.strip()

    return {
        "id": name,
        "name": display_name,
        "description": description[:500],
        "tags": tags,
        "as_tool": as_tool,
        "body": body,
    }


def resolve_skills(names: list[str], skills_dir: str = "skills") -> list[dict[str, Any]]:
    """Load multiple skills by name. Missing skills are skipped with a log warning."""
    skills = []
    for name in names:
        s = load_skill(name, skills_dir)
        if s:
            skills.append(s)
        else:
            logger.warning("Skill '%s' not found in %s/", name, skills_dir)
    return skills


def skills_to_prompt(skills: list[dict[str, Any]]) -> str:
    """Convert skill list to a system prompt block."""
    if not skills:
        return ""

    lines = ["## Active Skills"]
    for s in skills:
        lines.append(f"\n### {s['id']}")
        body = s["body"]
        if len(body) > MAX_PROMPT_PER_SKILL:
            body = body[:MAX_PROMPT_PER_SKILL] + "\n[...truncated]"
        lines.append(body)

    return "\n".join(lines)


def skills_to_tools(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tool definitions for skills with as_tool == true."""
    tools = []
    for s in skills:
        if not s.get("as_tool"):
            continue
        body = s["body"]
        _body_ref = body

        tools.append({
            "name": s["id"],
            "description": s["description"],
            "parameters": {
                "type": "object",
                "properties": {},
            },
            "execute": lambda p=None, ctx=None, b=_body_ref: b[:MAX_TOOL_OUTPUT],
        })
    return tools
