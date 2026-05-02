"""Dream process: analyze history and consolidate into MEMORY.md (nanobot Dream pattern)."""
import os
import json


DREAM_PROMPT_TEMPLATE = """You are a Dream processor for {agent_name}, an AI agent in the CocoCat team.

## Your Job
Analyze the following recent task history entries and extract important information to keep in long-term memory.

## What to Extract
1. **Key Decisions**: Important choices made during task execution
2. **Facts Learned**: New information about the system, tools, or processes
3. **Preferences**: Stated preferences for how things should be done
4. **Patterns**: Recurring patterns in tasks or results

## What to Ignore
- Routine acknowledgments
- Test messages and placeholders
- Trivial details

## History Entries
{history_entries}

## Output Format
Return your findings as bullet points prefixed with the current date.
Example:
### 2026-05-02 Dream Consolidation
- Decided to use Rust for the core engine due to performance requirements
- Learned that DeepSeek API requires reasoning_content to be passed back
"""


def get_cursor(agent_id: str) -> int:
    """Read the current dream cursor."""
    cursor_path = _agent_memory_dir(agent_id, ".dream_cursor")
    if not os.path.exists(cursor_path):
        return 0
    try:
        with open(cursor_path, "r") as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return 0


def set_cursor(agent_id: str, cursor: int):
    """Write the dream cursor."""
    cursor_path = _agent_memory_dir(agent_id, ".dream_cursor")
    os.makedirs(os.path.dirname(cursor_path), exist_ok=True)
    with open(cursor_path, "w") as f:
        f.write(str(cursor))


def get_unprocessed_history(agent_id: str) -> tuple[list[dict], int]:
    """Read history entries after the cursor. Returns (entries, total_count)."""
    since = get_cursor(agent_id)
    history_path = _agent_memory_dir(agent_id, "history.jsonl")
    if not os.path.exists(history_path):
        return [], 0

    entries = []
    with open(history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    unprocessed = entries[since:]
    return unprocessed, len(entries)


def run_dream(agent_id: str, agent_name: str, llm_client=None) -> str:
    """Execute the Dream process: analyze history, update MEMORY.md."""
    from llm import LLMClient

    llm = llm_client or LLMClient()
    unprocessed, total_entries = get_unprocessed_history(agent_id)

    if not unprocessed:
        return "No new history entries to process."

    history_text = ""
    for i, entry in enumerate(unprocessed):
        history_text += f"\n### Entry {i+1}\n"
        history_text += f"Task: {entry.get('prompt', '?')[:300]}\n"
        history_text += f"Result: {entry.get('response_summary', '?')[:300]}\n"
        history_text += f"Iterations: {entry.get('iterations', '?')}\n"

    from datetime import datetime
    prompt = DREAM_PROMPT_TEMPLATE.format(
        agent_name=agent_name,
        history_entries=history_text,
    )

    try:
        response = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        content = (response.get("content") or "").strip()
    except Exception as e:
        return f"Dream LLM call failed: {e}"

    if not content:
        return "Dream produced no output."

    # Phase 2: Use AgentLoop to surgically edit MEMORY.md
    from agent_loop import AgentLoop
    from tools import create_default_registry

    script_dir = os.path.dirname(os.path.abspath(__file__))
    agent_runtime_path = os.path.join(script_dir, "agent_runtime.py")
    tools = create_default_registry(agent_runtime_path=agent_runtime_path)

    mem_path = _agent_memory_dir(agent_id, "MEMORY.md")
    os.makedirs(os.path.dirname(mem_path), exist_ok=True)

    current_memory = ""
    if os.path.exists(mem_path):
        with open(mem_path, "r", encoding="utf-8") as f:
            current_memory = f.read()

    edit_prompt = f"""You are a memory consolidation agent. Your task is to update {agent_name}'s long-term memory file.

## Current MEMORY.md
{current_memory[:3000] if current_memory else "(empty)"}

## New Information to Incorporate
{content[:2000]}

## Instructions
1. Read the current MEMORY.md using the read_file tool
2. Merge the new information into MEMORY.md
3. Use the edit_file tool to make targeted edits
4. Remove outdated information if needed
5. Keep the file well-organized with clear section headings

Use read_file and edit_file tools to complete this task."""

    edit_loop = AgentLoop(agent_id=agent_id, agent_name=f"{agent_name}-dream", tools=tools)
    edit_loop.run(edit_prompt)

    set_cursor(agent_id, total_entries)
    entry_count = len(unprocessed)
    return f"Dream processed {entry_count} history entries. Memory updated via surgical editing."


def _agent_memory_dir(agent_id: str, filename: str = "") -> str:
    """Get path to an agent's memory file."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", agent_id, "memory")
    if filename:
        return os.path.join(base, filename)
    return base
