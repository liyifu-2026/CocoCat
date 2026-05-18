"""Agent builder — profile, skills, and prompt construction."""
from cococat.core.agent_builder.prompt import build_system_prompt, load_memory_from_agent_dir, KB_AGENT_STATIC_PREFIX, STATIC_PREFIX
from cococat.core.agent_builder.skills import resolve_skills, skills_to_prompt, skills_to_tools, load_skill
from cococat.core.agent_builder.profile import load_agent_system_prompt, get_agent_skills, load_agent_profile, profile_to_system_prompt

__all__ = [
    "build_system_prompt", "load_memory_from_agent_dir", "KB_AGENT_STATIC_PREFIX", "STATIC_PREFIX",
    "resolve_skills", "skills_to_prompt", "skills_to_tools", "load_skill",
    "load_agent_system_prompt", "get_agent_skills", "load_agent_profile", "profile_to_system_prompt",
]
