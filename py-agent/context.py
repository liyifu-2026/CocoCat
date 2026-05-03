"""System prompt builder (nanobot ContextBuilder pattern)."""
import os
import json


SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, a capable AI agent in the CocoCat multi-agent team.

## Identity
- Name: {agent_name}
- ID: {agent_id}
- Current Scene: {scene_name}{profile_section}

## Scene Context
{scene_context}

## Your Wiki Knowledge
{knowledge_overview}

## Active Skills
{agent_skills}

## Scene Skills
{env_skills}

## Your Long-Term Memory
{agent_memory}
{user_profile_section}{user_conversation_section}

## Capabilities
You have access to the following tools:
{tool_descriptions}

## Guidelines
1. You can use tools to read/write files, execute commands, and search the workspace.
2. When you need to delegate a subtask, use the sub_agent tool to spawn a child agent.
3. Use the remember tool to store important facts in long-term memory.
4. Use the recall tool to retrieve past memories.
5. When you complete a task, key information is automatically saved to your history.
6. Think step by step before using tools.
7. You work in the directory: {workspace}
"""


def build_system_prompt(
    agent_id: str = "unknown",
    agent_name: str = "Agent",
    tool_descriptions: str = "",
    workspace: str = "",
    scene_name: str = "default",
    scene_context: str = "General-purpose work environment.",
    agent_memory: str = "",
    agent_skills: str = "",
    env_skills: str = "",
    profile: dict | None = None,
    user_profile: str = "",
    user_conversation: str = "",
    knowledge_overview: str = "",
) -> str:
    profile_section = _build_profile_section(profile) if profile else ""
    if profile_section:
        profile_section = f"\n## Agent Profile\n{profile_section}"
    user_profile_section = f"\n## Current User\n{user_profile}" if user_profile else ""
    user_conversation_section = f"\n## Conversation History\n{user_conversation}" if user_conversation else ""
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_descriptions=tool_descriptions,
        workspace=workspace or os.getcwd(),
        scene_name=scene_name,
        scene_context=scene_context,
        agent_memory=agent_memory or "(No long-term memories yet)",
        agent_skills=agent_skills or "(No specific skills assigned)",
        env_skills=env_skills or "(No special skills for this scene)",
        profile_section=profile_section,
        user_profile_section=user_profile_section,
        user_conversation_section=user_conversation_section,
        knowledge_overview=knowledge_overview or "(No knowledge bases mounted)",
    )


def load_daily_log(agent_id: str, max_chars: int = 2000, max_entries: int = 5) -> str:
    """Load recent entries from today's daily log. Truncated to avoid context bloat."""
    base = os.path.dirname(os.path.abspath(__file__))
    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(base, "..", "agents", agent_id, "memory", "daily", f"{today}.md")
    if not os.path.exists(log_path):
        return ""
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception:
        return ""
    if not content:
        return ""
    # Keep only last N entries
    entries = [e.strip() for e in content.split("\n## ") if e.strip()]
    entries = entries[-max_entries:]
    result = "\n## ".join(entries)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n...(truncated)"
    return result


def load_user_profile(agent_id: str, user_id: str, base_dir: str = "") -> str:
    if not base_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    user_hash = _user_hash(user_id)
    profile_path = os.path.join(base_dir, "..", "agents", agent_id, "memory", "users", user_hash, "PROFILE.md")
    if not os.path.exists(profile_path):
        return ""
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _user_hash(user_id: str) -> str:
    """Duplicate of dream._user_hash to avoid circular import."""
    import hashlib
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def load_agent_profile(agent_id: str, base_dir: str = "") -> dict | None:
    """Load agent profile from agents/{agent_id}/profile.json."""
    if not base_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    profile_path = os.path.join(base_dir, "..", "agents", agent_id, "profile.json")
    if not os.path.exists(profile_path):
        return None
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _build_profile_section(profile: dict) -> str:
    """Format a profile dict into a string section for the system prompt."""
    lines = []
    if "role" in profile:
        lines.append(f"- Role: {profile['role']}")
    if "objective" in profile:
        lines.append(f"- Objective: {profile['objective']}")
    if "traits" in profile and profile["traits"]:
        lines.append(f"- Traits: {', '.join(profile['traits'])}")
    if "background" in profile and profile["background"]:
        lines.append(f"- Background: {profile['background']}")
    if "rules" in profile and profile["rules"]:
        lines.append("- Rules:")
        for rule in profile["rules"]:
            lines.append(f"  - {rule}")
    return "\n".join(lines)


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


def load_knowledge_overview(scene_id: str) -> str:
    """Load purpose.md and a trimmed index.md from mounted KBs for system prompt injection."""
    kbs = load_mounted_kbs(scene_id)
    if not kbs:
        return ""
    parts = []
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "knowledge")
    for kb_id in kbs:
        kb_path = os.path.join(base, kb_id)
        purpose_path = os.path.join(kb_path, "purpose.md")
        index_path = os.path.join(kb_path, "index.md")
        kb_parts = [f"=== {kb_id} ==="]
        if os.path.exists(purpose_path):
            try:
                with open(purpose_path, "r") as f:
                    purpose = f.read().strip()
                if purpose:
                    kb_parts.append(f"Purpose: {purpose[:300]}")
            except Exception:
                pass
        if os.path.exists(index_path):
            try:
                with open(index_path, "r") as f:
                    index_content = f.read().strip()
                lines = index_content.split("\n")
                trimmed = "\n".join(lines[:30])
                if trimmed:
                    kb_parts.append(f"Pages:\n{trimmed}")
            except Exception:
                pass
        parts.append("\n".join(kb_parts))
    return "\n\n".join(parts)


def load_agent_skills(agent_id: str, progressive: bool = True) -> str:
    import os as _os
    from skill_hub import get_skill_summary, check_skill_dependencies
    base = _os.path.dirname(_os.path.abspath(__file__))
    manifest_path = _os.path.join(base, "..", "agents", agent_id, "skills", "manifest.json")
    if not _os.path.exists(manifest_path):
        return ""

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return ""

    all_skill_names = manifest.get("public", []) + manifest.get("private", [])

    available = []
    for name in all_skill_names:
        ok, _missing = check_skill_dependencies(name)
        if ok:
            available.append(name)

    if not available:
        return ""

    if progressive:
        lines = ["You have the following skills available. Use read_file to view full content:"]
        for name in available:
            summary = get_skill_summary(name)
            for subdir in ["public", "private"]:
                path = _os.path.join(base, "..", "skills", subdir, f"{name}.md")
                if _os.path.exists(path):
                    lines.append(f"- {name}: {summary}  (`skills/{subdir}/{name}.md`)")
                    break
        return "\n".join(lines)
    else:
        parts = []
        for skill_name in available:
            for subdir in ["public", "private"]:
                skill_path = _os.path.join(base, "..", "skills", subdir, f"{skill_name}.md")
                if _os.path.exists(skill_path):
                    try:
                        with open(skill_path, "r", encoding="utf-8") as f:
                            content = f.read().strip()
                        if content:
                            parts.append(content)
                    except Exception:
                        pass
                    break
        if not parts:
            return ""
        return "\n\n---\n\n".join(parts)


def load_agent_memory(agent_id: str) -> str:
    """Load the agent's MEMORY.md for system prompt injection."""
    import os as _os
    mem_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "agents", agent_id, "memory", "MEMORY.md")
    if not _os.path.exists(mem_path):
        return ""
    try:
        with open(mem_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


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
