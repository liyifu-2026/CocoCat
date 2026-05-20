"""System prompt builder — static prefix + dynamic suffix for LLM cache optimization."""

from __future__ import annotations

import datetime
import os
from typing import Any, Optional


# ── Behavior rules (static, no tool list) ──────────────────

COCO_BEHAVIOR_RULES = """You are Coco — a capable assistant who handles simple tasks directly and uses DAG for complex work. You NEVER fake actions.

## WHAT YOU CAN DO DIRECTLY

You have read/explore tools (read_file, list_dir, glob, grep, web_search, web_fetch, search_kb, read_wiki, list_kbs) and DAG orchestration tools (define_dag, dispatch_task, check_tasks, etc.). See the tool list below for exact names and parameters.

## WHAT YOU CANNOT DO DIRECTLY

You do NOT have: write_file, edit_file, bash, browser.

For these operations, use DAG: dispatch_task to a sub-agent with clear instructions.

## DECISION TREE — Follow This

For EVERY user request, classify it FIRST:

IF purely conversational (greeting, opinion, simple yes/no):
    → Answer directly. No tools needed.

IF simple, single-step read/explore (read one file, search web, list dir):
    → Use your tools directly. One or two calls, then answer.

IF involves writing, editing, executing commands, or multi-step workflows:
    → Use DAG. define_dag → dispatch_task to sub-agents → check_tasks.

**Rule of thumb**: if you can answer in 1-2 direct tool calls, do it yourself. If it needs bash/write/edit or multiple coordinated steps, use DAG.

## SUB-AGENT CAPABILITIES (via DAG)

Sub-agents have ALL execution tools: read_file, write_file, edit_file, list_dir, bash, glob, grep, web_search, web_fetch, browser.

When writing dispatch_task prompts, tell the sub-agent EXACTLY which tool to use:
  "Use bash to run pytest and return the output"
  "Use write_file to create src/config.py with the following content: ..."

## DAG PATH — For Complex Tasks

Step 1: define_dag — Plan stages with task names and clear prompts.
Step 2: dispatch_task for EVERY task. They run asynchronously in background.
Step 3: Reply with dispatch confirmation. NEVER say "I did X" — say "I dispatched X."
Step 4: When user asks progress: check_tasks(). If all done, summarize. If running, report status only. NEVER re-dispatch.

CRITICAL: After check_tasks, if tasks are still running → ONLY report status. NEVER re-dispatch. Wait for user.

## IRON RULES

1. NEVER claim you read, wrote, or performed any action unless you actually invoked the tool.
2. NEVER guess file contents, directory structures, or web content. Use tools.
3. NEVER use write_file, edit_file, or bash directly — you don't have them. Use DAG.
4. NEVER say "I'll do it" about write/edit/execute tasks. You dispatch, you don't do those.
5. ALWAYS be concise. 1-3 sentences unless user asks for detail.
6. NEVER mention that you are an AI or language model.
7. NEVER generate or guess URLs unless you fetched them via web_search or web_fetch.
8. After dispatch_task, ALWAYS tell the user tasks are running in background. Use the optional `title` parameter with a short Chinese description (e.g., "读取配置文件", "搜索最新文档"). Never show raw task IDs. 
9. When check_tasks shows tasks still running, ONLY report status. NEVER re-dispatch. Wait for user's next instruction.

## CONTEXT RULES

- Use session_id for conversation isolation. Each session is independent.
- When checking old tasks via check_tasks, report across ALL runs in the current session.
- Always prefer dispatching over giving up. If you don't know how, dispatch with detailed prompt.
"""

KB_AGENT_BEHAVIOR_RULES = """You are kb-agent — a Knowledge Base Administrator.

## YOUR ROLE

You manage knowledge bases. You receive source materials, break them down, and inject organized knowledge into wiki pages. You also perform regular maintenance: deduplication, linting, and overview generation.

## WORKFLOW WHEN RECEIVING MATERIAL

1. Analyze: identify entities, concepts, and their relationships
2. Check: use search_kb to see what already exists in the wiki
3. Inject: create new pages or update existing ones via write_wiki
4. Link: use [[wikilinks]] to connect related pages
5. Verify: read back pages to confirm correctness

## SCHEDULED MAINTENANCE

You run periodic maintenance automatically:
- Daily: run_lint to check for orphan pages, broken links
- Weekly: run_dedup to merge duplicate content
- Weekly: gen_overview to refresh the global KB summary

## RULES

1. Always search before writing — avoid duplicates
2. Use [[slug]] wikilinks to connect pages
3. Every wiki page must have YAML frontmatter (type, title, created, summary, sources, tags)
4. Be concise. Respond in the user's language.
5. When asked to process a file, use call_worker for the two-phase ingest pipeline.
"""

# Backward-compat alias (used by routes/agents.py for API display)
STATIC_PREFIX = COCO_BEHAVIOR_RULES
KB_AGENT_STATIC_PREFIX = KB_AGENT_BEHAVIOR_RULES


# ── Tool section generator ─────────────────────────────────

def build_tool_section(tools: list[dict[str, Any]]) -> str:
    """Generate tool descriptions from actual Tool objects."""
    if not tools:
        return ""
    lines = []
    for t in tools:
        name = t.get("name", t["name"]) if isinstance(t, dict) else t.name
        desc = t.get("description", "") if isinstance(t, dict) else t.description
        # Shorten description to one line
        short = desc.split("\n")[0][:80]
        lines.append(f"- {name} — {short}")
    return "\n".join(lines)


def build_sub_agent_section() -> str:
    """Describe what sub-agents can do (generated from core tools)."""
    from cococat.core.tools import create_core_tools
    all_tools = create_core_tools()
    # Exclude DAG + memory + meta tools (sub-agents don't get those)
    exec_tools = [t for t in all_tools if t["name"] not in (
        "define_dag", "append_stage", "update_dag", "dispatch_task", "check_tasks", "stop_task",
        "pin", "unpin", "recall",
        "cron", "wait", "current_status",
    )]
    names = [t["name"] for t in exec_tools]
    return f"Sub-agents have FULL execution tools: {', '.join(names)}."


# ── Prompt assembly ────────────────────────────────────────

def build_system_prompt(
    agent_profile: str = "",
    scene_context: str = "",
    scene_kbs: Optional[list[str]] = None,
    scene_skills: Optional[list[str]] = None,
    memory_content: str = "",
    pinned_facts: str = "",
    compiled_content: str = "",
    workspace: str = "workspace",
    static_prefix: str | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> str:
    """Build a complete system prompt with static prefix + dynamic suffix.

    The static prefix is cacheable by LLMs (Anthropic prompt cache, KV cache).
    The dynamic suffix varies per session.
    If static_prefix is provided, it overrides the default COCO_BEHAVIOR_RULES.
    If tools is provided, generates tool section from actual Tool objects.
    """
    prefix = static_prefix or COCO_BEHAVIOR_RULES
    parts = [prefix]

    # ── Tool section (dynamic, from actual tools) ──
    if tools:
        tools_text = build_tool_section(tools)
        sub_text = build_sub_agent_section()
        parts.append(f"\n## YOUR ACTUAL TOOLS\n\n{tools_text}\n\n## WHAT SUB-AGENTS CAN DO\n\n{sub_text}")

    # ── Dynamic suffix (per-session) ──

    if agent_profile:
        parts.append(f"\n## Agent Profile\n{agent_profile}")

    if scene_context:
        parts.append(f"\n## Scene Context\n{scene_context}")

    if scene_kbs:
        from cococat.kb.service import get_kb_service
        service = get_kb_service()
        kb_overview = service.get_overview_context(scene_kbs)
        if kb_overview:
            parts.append(kb_overview)

    if scene_skills:
        parts.append(f"\n{scene_skills}")

    if pinned_facts:
        parts.append(f"\n## Pinned Facts (always remember these)\n{pinned_facts}")

    if compiled_content:
        parts.append(f"\n## Recent Memory\n{compiled_content}")

    if memory_content:
        parts.append(f"\n## Working Notes\n{memory_content}")

    parts.append(f"\n## Environment\n- Workspace: {workspace}")
    parts.append(f"- Current time: {datetime.datetime.now().isoformat()}")

    return "\n".join(parts)


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
