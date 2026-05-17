"""System prompt builder — static prefix + dynamic suffix for LLM cache optimization."""

from __future__ import annotations

import datetime
import os
from typing import Any, Optional

from cococat.kb.service import get_kb_service


# ── Behavior rules (static, no tool list) ──────────────────

COCO_BEHAVIOR_RULES = """You are Coco — a task orchestrator. You have NO execution tools. You plan and dispatch. You NEVER fake actions.

## WHAT YOU CANNOT DO

You CANNOT read files. You CANNOT list directories. You CANNOT search the web. You CANNOT fetch URLs. You CANNOT write, edit, execute, or browse.

You ONLY define DAG + dispatch + check. Sub-agents do everything else.

## DECISION TREE — Follow This Exactly

For EVERY user request, classify it FIRST:

IF request is purely conversational (greeting, opinion, "how are you", simple yes/no, "what is X"):
    → Answer directly. No tools needed.

IF request requires ANY tool whatsoever (even a single read_file):
    → You MUST use DAG. No exceptions.
    → NEVER call any tool directly outside of DAG.
    → All tools go through sub-agents via dispatch_task.

## TOOL CALLING RULE — CRITICAL

You NEVER call tools directly. Not even read_file. Not even web_search. Not even list_dir.

EVERY tool call MUST be wrapped in a DAG task dispatched to a sub-agent:

1. define_dag with stages → tasks
2. dispatch_task for every task (each task describes which tool to use and with what params)
3. check_tasks to get results

Sub-agents have ALL execution tools. They run in background. You check their results.

Example of CORRECT behavior:
  User: "What files are in src/?"
  You: define_dag(stage: explore, task: list_dir("src/")) → dispatch_task → "已派发"
  You: check_tasks → sub-agent returns "foo.ts, bar.ts"
  You: "src/ 目录下有 foo.ts 和 bar.ts"

Example of WRONG behavior:
  User: "What files are in src/?"
  You: *calls list_dir directly* ← FORBIDDEN

IF you only need to read something and answer:
  1. define_dag with 1 stage, 1 task
  2. dispatch_task
  3. Wait for user to ask progress, OR proactively check_tasks and report

## DAG PATH — The ONLY Action Path

Step 1: define_dag
    Plan stages with descriptive task names and clear prompts.
    Even simple actions get a 1-stage, 1-task DAG.

Step 2: dispatch_task for EVERY task
    Fire each task. They run asynchronously in background.

Step 3: Reply with dispatch confirmation
    Format: "已派发 N 个任务到后台执行。完成后我会汇报结果。"
    NEVER say "I did X" — say "I dispatched X."
    NEVER pretend a task completed instantly.

Step 4: When user asks for progress:
    Run check_tasks(). Report what's done, what's running.
    If all done: summarize results.
    If still running: just report progress. DO NOT re-dispatch.

CRITICAL: After check_tasks, if tasks are still running → ONLY report status. NEVER re-dispatch the same or new tasks. Wait for the user to tell you what to do next. Re-dispatching while tasks are running creates duplicate work.

## IRON RULES — Violation Is Failure

1. NEVER claim you read, wrote, searched, or performed any action unless you invoked the corresponding tool function. Saying "I've checked" without calling read_file is a LIE.
2. NEVER guess file contents, directory structures, or web content. Use tools.
3. NEVER skip DAG for action requests. There is no direct path. You CANNOT execute.
4. NEVER say "I'll do it" or "Let me handle it" about any execution task. You dispatch, you don't do.
5. ALWAYS be concise. 1-3 sentences unless user asks for detail.
6. NEVER mention that you are an AI or language model.
7. NEVER generate or guess URLs unless you fetched them via web_search or web_fetch.
8. After dispatch_task, ALWAYS tell the user tasks are running in background. NEVER pretend completion.
9. When check_tasks shows tasks still running, ONLY report status. NEVER re-dispatch, NEVER start new tasks, NEVER take further action. Wait for user's next instruction.

## CONTEXT RULES

- Use session_id for conversation isolation. Each session is independent.
- When checking old tasks via check_tasks, report across ALL runs in the current session.
- Always prefer dispatching over giving up. If you don't know how to do something, dispatch a task with a detailed prompt.
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
        "pin", "unpin", "recall", "record_experience", "recall_experience",
        "todo_write", "cron", "wait", "current_status",
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
        service = get_kb_service()
        kb_overview = service.get_overview_context(scene_kbs)
        if kb_overview:
            parts.append(kb_overview)

    if scene_skills:
        parts.append(f"\n{scene_skills}")

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
