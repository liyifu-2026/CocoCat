"""System prompt builder — static prefix + dynamic suffix for LLM cache optimization."""

from __future__ import annotations

import datetime
import os
from typing import Optional

from cococat.kb import load_kb_overview

STATIC_PREFIX = """You are a CocoCat AI agent — part of a multi-agent collaboration platform.

## Core Rules
- Be concise and direct. Answer the user's question without unnecessary preamble.
- Use tools when you need to read files, search, or execute commands.
- When a task is complex or parallelizable, use sub_agent to delegate.
- Never mention that you are an AI or language model.
- If you don't know something, say so — don't fabricate.

## Tool Usage
- read_file: read any file. Use offset/limit for large files.
- write_file: create or overwrite a file. Creates parent directories.
- edit_file: replace text in a file. The old string must match exactly.
- list_dir: browse directories.
- bash: execute shell commands. Be careful with destructive operations.
- glob/grep: search files by pattern.
- web_search/web_fetch: access the internet.
- sub_agent: delegate to another agent (async, fire-and-forget).
- check_tasks/stop_task: manage pending sub-agent tasks.
- todo_write: track your task progress.
- recall: search conversation memory (FTS5 full-text).
- pin/unpin: manage pinned facts for persistent context.
- record_experience/recall_experience: track categorized experiences.
- cron: schedule recurring tasks.
- current_status: check your runtime state.
- wait: pause between operations.

## Safety
- Never execute destructive commands without user confirmation.
- Path traversal is blocked — do not attempt it.
- When bound to a scene, file access is limited to that scene's KB directories and workspace.
"""


def build_system_prompt(
    agent_profile: str = "",
    scene_context: str = "",
    scene_kbs: Optional[list[str]] = None,
    scene_skills: Optional[list[str]] = None,
    memory_content: str = "",
    pinned_facts: str = "",
    workspace: str = "workspace",
) -> str:
    """Build a complete system prompt with static prefix + dynamic suffix.

    The static prefix is cacheable by LLMs (Anthropic prompt cache, KV cache).
    The dynamic suffix varies per session.
    """
    parts = [STATIC_PREFIX]

    # ── Dynamic suffix (per-session) ──

    if agent_profile:
        parts.append(f"\n## Agent Profile\n{agent_profile}")

    if scene_context:
        parts.append(f"\n## Scene Context\n{scene_context}")

    if scene_kbs:
        kb_overview = load_kb_overview(scene_kbs)
        if kb_overview:
            parts.append(kb_overview)

    if scene_skills:
        skills_text = "\n".join(f"- {s}" for s in scene_skills)
        parts.append(f"\n## Scene Skills\n{skills_text}")

    if memory_content:
        parts.append(f"\n## Memory\n{memory_content}")

    if pinned_facts:
        parts.append(f"\n## Pinned Facts (always remember these)\n{pinned_facts}")

    parts.append(f"\n## Environment\n- Workspace: {workspace}")
    parts.append(f"- Current time: {datetime.datetime.now().isoformat()}")

    return "\n".join(parts)


def load_memory_from_agent_dir(agent_dir: str) -> tuple[str, str]:
    """Load memory.md and pinned.md from an agent directory.

    Returns (memory_content, pinned_facts). Empty strings if files don't exist.
    """
    memory_content = ""
    pinned = ""

    memory_path = os.path.join(agent_dir, "memory", "memory.md")
    if os.path.exists(memory_path):
        try:
            with open(memory_path, encoding="utf-8") as f:
                memory_content = f.read(3000)
        except OSError:
            pass

    pinned_path = os.path.join(agent_dir, "pinned.md")
    if os.path.exists(pinned_path):
        try:
            with open(pinned_path, encoding="utf-8") as f:
                pinned = f.read(2000)
        except OSError:
            pass

    return memory_content, pinned
