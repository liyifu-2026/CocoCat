"""Skills routes."""
import os
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel

from cococat.skills import load_skill, resolve_skills

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    content: str


@router.get("")
async def list_skills(request: Request, tag: str | None = Query(None)):
    """List all skills from skills/ directory. Optional tag filter."""
    skills_dir = "skills"
    result: list[dict] = []

    if not os.path.isdir(skills_dir):
        return {"skills": result}

    for fname in sorted(os.listdir(skills_dir)):
        if not fname.endswith(".md"):
            continue
        name = fname[:-3]
        s = load_skill(name)
        if not s:
            continue
        if tag and tag not in s.get("tags", []):
            continue
        result.append({
            "name": s["name"],
            "id": s["id"],
            "description": s["description"][:100],
            "tags": s.get("tags", []),
            "as_tool": s.get("as_tool", False),
        })

    return {"skills": result}


@router.get("/{skill_name}")
async def get_skill(skill_name: str):
    """Read a single skill's markdown content."""
    path = os.path.join("skills", f"{skill_name}.md")
    if not os.path.exists(path):
        return {"error": "not found"}, 404

    skill = load_skill(skill_name)
    if not skill:
        return {"error": "failed to load"}, 500

    return {
        "id": skill["id"],
        "name": skill["name"],
        "description": skill["description"],
        "tags": skill["tags"],
        "as_tool": skill["as_tool"],
        "body": skill["body"],
    }
