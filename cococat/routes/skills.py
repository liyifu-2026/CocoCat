"""Skills routes."""
import os
from fastapi import APIRouter, Request
from pydantic import BaseModel

from cococat.skills import load_global_skills, load_scene_skills, load_skill_file

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    content: str


@router.get("")
async def list_skills(request: Request):
    """List all skills (global + per-scene)."""
    global_skills = load_global_skills()
    result = {"global": []}

    for s in global_skills:
        result["global"].append({"name": s["name"], "description": s["description"][:100]})

    # Scene skills
    scenes_dir = "skills/scenes"
    if os.path.isdir(scenes_dir):
        for scene_id in os.listdir(scenes_dir):
            skipath = os.path.join(scenes_dir, scene_id)
            if os.path.isdir(skipath):
                scene = load_scene_skills(scene_id)
                if scene:
                    result.setdefault("scenes", {})
                    result["scenes"][scene_id] = [
                        {"name": s["name"], "description": s["description"][:100]}
                        for s in scene
                    ]

    return result


@router.get("/{skill_name}")
async def get_skill(skill_name: str):
    """Read a skill's markdown content."""
    # Search global
    path = os.path.join("skills", "public", f"{skill_name}.md")
    if not os.path.exists(path):
        # Search scene skills
        for scene_dir in ["skills/scenes"]:
            if not os.path.isdir(scene_dir):
                continue
            for scene_id in os.listdir(scene_dir):
                sp = os.path.join(scene_dir, scene_id, f"{skill_name}.md")
                if os.path.exists(sp):
                    path = sp
                    break

    if not os.path.exists(path):
        return {"error": "not found"}, 404

    skill = load_skill_file(path)
    if not skill:
        return {"error": "failed to load"}, 500

    return {
        "name": skill["name"],
        "description": skill["description"],
        "body": skill["body"],
    }
