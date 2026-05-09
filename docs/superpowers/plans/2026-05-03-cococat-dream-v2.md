# Two-Layer Dream Enhancement Plan

**Goal:** Upgrade Dream from single-phase append to two-phase: analyze → surgically edit MEMORY.md with tools.

**Architecture:** Phase 1 (existing): LLM analyzes history entries → extracts facts/decisions. Phase 2 (new): An AgentLoop with read_file/edit_file tools edits MEMORY.md precisely instead of appending blindly.

---

### Task 1: Add Phase 2 to Dream

**Files:**
- Modify: `py-agent/dream.py`

- [ ] **Step 1: Read current dream.py**

Find `run_dream()` function. After Phase 1 produces analysis content, instead of appending to MEMORY.md, feed the analysis to an AgentLoop that uses read_file + edit_file to surgically edit the file.

Replace the end of `run_dream()` from `if not content: return "Dream produced no output."` onwards:

```python
    if not content:
        return "Dream produced no output."

    # Phase 2: Use AgentLoop to surgically edit MEMORY.md
    from agent_loop import AgentLoop
    from tools import create_default_registry

    script_dir = os.path.dirname(os.path.abspath(__file__))
    agent_runtime_path = os.path.join(script_dir, "agent_runtime.py")
    tools = create_default_registry(agent_runtime_path=agent_runtime_path)

    edit_prompt = f"""You are a memory consolidation agent. Your task is to update {agent_name}'s long-term memory file.

## Current MEMORY.md
{read_text(mem_path) if os.path.exists(mem_path) else "(empty)"}

## New Information to Incorporate
{content}

## Instructions
1. Read the current MEMORY.md
2. Merge the new information into MEMORY.md
3. Use edit_file to make targeted edits
4. Remove outdated information if needed
5. Keep the file well-organized

Use read_file and edit_file tools to complete this task."""

    edit_loop = AgentLoop(agent_id=agent_id, agent_name=f"{agent_name}-dream", tools=tools)
    edit_loop.run(edit_prompt)

    set_cursor(agent_id, total_entries)
    entry_count = len(unprocessed)
    return f"Dream processed {entry_count} history entries. Memory updated via surgical editing."
```

- [ ] **Step 2: Build and test**

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/dream.py
git commit -m "feat: two-layer Dream with surgical MEMORY.md editing"
```
