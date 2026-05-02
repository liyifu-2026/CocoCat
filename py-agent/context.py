"""System prompt builder (nanobot ContextBuilder pattern)."""
import os
import json


SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, a capable AI agent in the CocoCat multi-agent team.

## Identity
- Name: {agent_name}
- ID: {agent_id}
- Current Scene: {scene_name}

## Scene Context
{scene_context}

## Active Skills
{env_skills}

## Capabilities
You have access to the following tools:
{tool_descriptions}

## Guidelines
1. You can use tools to read/write files, execute commands, and search the workspace.
2. When you need to delegate a subtask, use the sub_agent tool to spawn a child agent.
3. Think step by step before using tools.
4. When you have completed the task, provide a clear summary of what was done.
5. You work in the directory: {workspace}
"""


def build_system_prompt(
    agent_id: str = "unknown",
    agent_name: str = "Agent",
    tool_descriptions: str = "",
    workspace: str = "",
    scene_name: str = "default",
    scene_context: str = "General-purpose work environment.",
    env_skills: str = "",
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_descriptions=tool_descriptions,
        workspace=workspace or os.getcwd(),
        scene_name=scene_name,
        scene_context=scene_context,
        env_skills=env_skills or "(No special skills for this scene)",
    )


def load_scene_context(scene_id: str) -> tuple[str, str]:
    """Load scene name and CONTEXT.md content from scenes/{scene_id}/."""
    scene_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scenes", scene_id)
    name = scene_id
    context = ""
    context_path = os.path.join(scene_dir, "CONTEXT.md")
    if os.path.exists(context_path):
        with open(context_path, "r", encoding="utf-8") as f:
            context = f.read()
        first_line = context.strip().split("\n")[0].strip()
        if first_line.startswith("# "):
            name = first_line[2:].strip()
    return name, context


def load_env_skills(scene_id: str) -> str:
    """Load env-tagged skills from scenes/{scene_id}/skills/manifest.json and their .md files."""
    scene_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scenes", scene_id)
    manifest_path = os.path.join(scene_dir, "skills", "manifest.json")

    if not os.path.exists(manifest_path):
        return ""

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return ""

    env_skills = manifest.get("env_skills", [])
    if not env_skills:
        return ""

    parts = []
    for skill_name in env_skills:
        skill_path = os.path.join(scene_dir, "skills", f"{skill_name}.md")
        if os.path.exists(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                parts.append(content)

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)


def load_mounted_kbs(scene_id: str) -> list[str]:
    """Return list of KB IDs mounted to this scene."""
    import os as _os
    scene_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "scenes", scene_id)
    mount_path = _os.path.join(scene_dir, "mounted_kbs.json")
    if not _os.path.exists(mount_path):
        return []
    try:
        with open(mount_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("mounted", [])
    except Exception:
        return []


def build_tool_descriptions(tools: list[dict]) -> str:
    """Build a human-readable tool list from OpenAI-style tool definitions."""
    lines = []
    for t in tools:
        name = t["function"]["name"]
        desc = t["function"]["description"]
        params = t["function"]["parameters"]
        required = params.get("required", [])
        props = params.get("properties", {})
        param_lines = []
        for pname, pinfo in props.items():
            req = "required" if pname in required else "optional"
            param_lines.append(f"    {pname} ({req}): {pinfo.get('description', '')}")
        param_str = "\n" + "\n".join(param_lines) if param_lines else ""
        lines.append(f"- {name}: {desc}{param_str}")
    return "\n".join(lines)
