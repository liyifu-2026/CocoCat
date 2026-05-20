"""System prompt builder — loads system prompt from Mode YAML."""

from __future__ import annotations

import os
from typing import Any


# ── Tool section generator ─────────────────────────────────

def build_tool_section(tools: list[dict[str, Any]]) -> str:
    """Generate tool descriptions from actual Tool objects."""
    if not tools:
        return ""
    lines = []
    for t in tools:
        name = t.get("name", t["name"]) if isinstance(t, dict) else t.name
        desc = t.get("description", "") if isinstance(t, dict) else t.description
        short = desc.split("\n")[0][:80]
        lines.append(f"- {name} — {short}")
    return "\n".join(lines)


def build_sub_agent_section() -> str:
    """Describe what sub-agents can do (generated from core tools)."""
    from cococat.core.tools import create_core_tools
    all_tools = create_core_tools()
    exec_tools = [t for t in all_tools if t["name"] not in (
        "define_dag", "append_stage", "update_dag", "dispatch_task", "check_tasks", "stop_task",
        "pin", "unpin", "recall",
        "cron", "wait", "current_status",
    )]
    names = [t["name"] for t in exec_tools]
    return f"Sub-agents have FULL execution tools: {', '.join(names)}."


# ── Prompt assembly ────────────────────────────────────────

def build_system_prompt(mode_id: str = "default",
                        scene_context: str | None = None,
                        scene_kbs: list | None = None,
                        scene_skills: list | None = None,
                        memory_content: str | None = None,
                        pinned_facts: str | None = None,
                        compiled_content: str | None = None,
                        tools: list | None = None) -> str:
    from cococat.core.modes import load_mode
    mode = load_mode(mode_id)
    parts = [mode.system_prompt]

    if scene_context:
        parts.append(f"\n## 当前场景上下文\n{scene_context}")
    if scene_kbs:
        parts.append(f"\n## 可用知识库\n" + "\n".join(f"- {kb}" for kb in scene_kbs))
    if memory_content:
        parts.append(f"\n## 记忆\n{memory_content}")
    if pinned_facts:
        parts.append(f"\n## 置顶事实\n{pinned_facts}")
    if compiled_content:
        parts.append(f"\n## 编译记忆\n{compiled_content}")
    if tools:
        parts.append(build_tool_section(tools))

    return "\n\n".join(parts)


def load_memory_from_agent_dir(agent_dir: str) -> tuple[str, str, str]:
    """Load memory.md, pinned.md, and compiled memory from an agent directory.

    Returns (memory_content, pinned_facts, compiled_content).
    """
    memory_content = ""
    pinned = ""
    compiled = ""

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

    compiled_dir = os.path.join(agent_dir, "memory", "compiled")
    if os.path.isdir(compiled_dir):
        files = sorted(
            f for f in os.listdir(compiled_dir)
            if f.endswith(".md") and not f.startswith(".")
        )
        day_files = [f for f in files if not f.startswith("20") or len(f) < 12]
        week_files = [f for f in files if "-W" in f]
        longterm_files = [f for f in files if "longterm" in f]
        selected = day_files[-3:] + week_files[-2:] + longterm_files[-1:]
        for fname in selected:
            try:
                with open(os.path.join(compiled_dir, fname), encoding="utf-8") as f:
                    compiled += f"\n--- {fname} ---\n" + f.read(2000)
            except OSError:
                pass

    return memory_content, pinned, compiled
