"""Agent profile — loads agent identity from profile.yaml."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("cococat.profile")


def load_agent_profile(agent_dir: str) -> dict:
    """Load agent identity from profile.yaml or identity.md."""
    profile: dict = {"name": os.path.basename(agent_dir), "role": "sub"}

    # Try profile.yaml first
    yaml_path = os.path.join(agent_dir, "profile.yaml")
    if os.path.exists(yaml_path):
        try:
            import yaml
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                profile.update(data)
                return profile
        except (yaml.YAMLError, OSError):
            pass

    # Try identity.md fallback
    md_path = os.path.join(agent_dir, "identity.md")
    if os.path.exists(md_path):
        try:
            with open(md_path, encoding="utf-8") as f:
                content = f.read()
            profile["identity"] = content[:2000]
            # Extract name from first heading
            for line in content.split("\n"):
                if line.startswith("# "):
                    profile["name"] = line[2:].strip()
                    break
        except OSError:
            pass

    return profile


def profile_to_system_prompt(profile: dict) -> str:
    """Convert a profile dict to a system prompt snippet."""
    lines = []

    if profile.get("name"):
        lines.append(f"Your name is {profile['name']}.")
    if profile.get("role"):
        lines.append(f"Your role: {profile['role']}.")
    if profile.get("identity"):
        lines.append(f"\n{profile['identity']}")
    if profile.get("personality"):
        lines.append(f"\nPersonality: {profile['personality']}")

    return "\n".join(lines)


def load_agent_system_prompt(agent_dir: str) -> str:
    """Load agent profile and convert to system prompt."""
    profile = load_agent_profile(agent_dir)
    return profile_to_system_prompt(profile)


def get_agent_skills(agent_dir: str) -> list[str]:
    """Extract skill names from agent's profile.yaml."""
    if not agent_dir:
        return []
    profile = load_agent_profile(agent_dir)
    return profile.get("skills") or []
