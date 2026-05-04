"""Dream process: analyze history and consolidate into MEMORY.md (nanobot Dream pattern)."""
import os
import json
import time
import hashlib
import threading
_dream_lock = threading.Lock()


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


DREAM_COUNT_MIN = 3
DREAM_COUNT_MAX = 10
DREAM_TOKEN_PER_ENTRY = 2000
DREAM_TIME_TRIGGER = 1800  # 30 minutes in seconds


def should_trigger_dream(unprocessed_entries: list, last_dream_time: float, now: float) -> bool:
    if not unprocessed_entries:
        return False
    total_chars = 0
    for e in unprocessed_entries:
        content = e.get("content", "") if isinstance(e, dict) else str(e)
        total_chars += len(content)

    if now - last_dream_time >= DREAM_TIME_TRIGGER:
        return True

    if total_chars // DREAM_TOKEN_PER_ENTRY >= DREAM_COUNT_MIN:
        return True

    if len(unprocessed_entries) >= DREAM_COUNT_MIN and now - last_dream_time >= DREAM_TIME_TRIGGER // DREAM_COUNT_MIN:
        return True

    return False


def read_last_dream_time(agent_id: str) -> float:
    cursor_path = _agent_memory_dir(agent_id, ".dream_cursor")
    try:
        return os.path.getmtime(cursor_path)
    except OSError:
        return 0.0


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


def get_user_memory_dir(agent_id: str, user_hash: str) -> str:
    base = _agent_memory_dir(agent_id)
    return os.path.join(base, "users", user_hash)


def append_user_history(agent_id: str, user_hash: str, entry: dict):
    user_dir = get_user_memory_dir(agent_id, user_hash)
    os.makedirs(user_dir, exist_ok=True)
    history_path = os.path.join(user_dir, "history.jsonl")
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_unprocessed_history(agent_id: str, user_hash: str = "") -> tuple[list, int]:
    if user_hash:
        return _get_unprocessed_for_user(agent_id, user_hash)
    return _get_unprocessed_global(agent_id)


def _get_unprocessed_for_user(agent_id: str, user_hash: str) -> tuple[list, int]:
    user_dir = get_user_memory_dir(agent_id, user_hash)
    history_path = os.path.join(user_dir, "history.jsonl")
    cursor_path = os.path.join(user_dir, ".dream_cursor")
    cursor = _read_cursor(cursor_path)
    entries = _read_entries(history_path)
    unprocessed = entries[cursor:]
    return unprocessed, len(entries)


def _get_unprocessed_global(agent_id: str) -> tuple[list, int]:
    since = get_cursor(agent_id)
    history_path = _agent_memory_dir(agent_id, "history.jsonl")
    entries = _read_entries(history_path)
    unprocessed = entries[since:]
    return unprocessed, len(entries)


def _read_cursor(path: str) -> int:
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def _read_entries(path: str) -> list:
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def run_dream(agent_id: str, agent_name: str, llm_client=None) -> str:
    """Execute the Dream process: analyze history, update MEMORY.md."""
    if not _dream_lock.acquire(blocking=False):
        return "Dream already in progress, skipped."
    try:
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

        # Phase 2: Use AgentLoop to surgically edit MEMORY.md (restricted to file tools only)
        from agent_loop import AgentLoop
        from tools import ToolRegistry, ReadFileTool, EditFileTool

        tools = ToolRegistry()
        tools.register(ReadFileTool())
        tools.register(EditFileTool())

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
        try:
            from git_store import GitStore
            GitStore(_agent_memory_dir(agent_id)).commit(f"dream: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            pass
        entry_count = len(unprocessed)
        return f"Dream processed {entry_count} history entries. Memory updated via surgical editing."
    finally:
        _dream_lock.release()


def run_user_dream(agent_id: str, agent_name: str, user_hash: str, llm_client=None) -> str:
    from llm import LLMClient
    llm = llm_client or LLMClient()
    user_dir = get_user_memory_dir(agent_id, user_hash)
    history_path = os.path.join(user_dir, "history.jsonl")
    profile_path = os.path.join(user_dir, "PROFILE.md")
    entries, total = get_unprocessed_history(agent_id, user_hash=user_hash)
    if not entries:
        return "No new entries to process."

    history_text = json.dumps(entries, ensure_ascii=False, indent=2)[:4000]
    analysis_prompt = f"""Analyze these conversation entries and extract user preferences, habits, important facts about this user.
Write concise bullet points for their PROFILE.md file.

{history_text}"""
    try:
        analysis = llm.chat(messages=[{"role": "user", "content": analysis_prompt}], max_tokens=512, temperature=0.3)
        content = (analysis.get("content") or "").strip()
    except Exception as e:
        return f"User dream LLM call failed: {e}"

    if not content:
        return "User dream produced no output."

    os.makedirs(user_dir, exist_ok=True)
    with open(profile_path, "a", encoding="utf-8") as f:
        f.write(f"\n## Dream Consolidation ({time.strftime('%Y-%m-%d')})\n")
        f.write(content + "\n")

    with open(os.path.join(user_dir, ".dream_cursor"), "w") as f:
        f.write(str(total))

    try:
        from git_store import GitStore
        GitStore(user_dir).commit(f"dream-user: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:
        pass

    return f"User dream processed {len(entries)} entries, updated PROFILE.md."


def _agent_memory_dir(agent_id: str, filename: str = "") -> str:
    """Get path to an agent's memory file."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", agent_id, "memory")
    if filename:
        return os.path.join(base, filename)
    return base
