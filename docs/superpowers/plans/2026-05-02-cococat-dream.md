# Dream Consolidator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** The `dream` tool actually works — it reads unprocessed history from `history.jsonl`, uses LLM to extract key facts/decisions, and updates `MEMORY.md` with the consolidated findings. A `.dream_cursor` file tracks which entries have been processed.

**Architecture:** New `dream.py` module handles the Dream process: reads history entries after the cursor, calls LLM with an analysis prompt, formats findings, and appends to MEMORY.md. The `dream` tool triggers this process. Auto-Dream triggers after every 3 tasks.

---

## File Structure

```
Cococlaw/
├── agents/
│   ├── leader/memory/
│   │   ├── MEMORY.md         # Updated by Dream
│   │   ├── history.jsonl     # Read by Dream
│   │   └── .dream_cursor     # NEW: tracking cursor
│   ├── employee_a/memory/
│   │   └── .dream_cursor     # NEW
│   └── employee_b/memory/
│       └── .dream_cursor     # NEW
├── py-agent/
│   ├── dream.py              # NEW: Dream processor
│   ├── tools.py              # MODIFIED: DreamTool triggers real Dream
│   └── agent_loop.py         # MODIFIED: auto-Dream after 3 entries
```

---

### Task 1: Create dream.py module

**Files:**
- Create: `py-agent/dream.py`
- Create: cursor files for all agents

- [ ] **Step 1: Create cursor files**

```powershell
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\leader\memory\.dream_cursor" | Out-Null
Set-Content -Path "C:\Users\12991\Desktop\Cococlaw\agents\leader\memory\.dream_cursor" -Value "0"
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_a\memory\.dream_cursor" | Out-Null
Set-Content -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_a\memory\.dream_cursor" -Value "0"
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_b\memory\.dream_cursor" | Out-Null
Set-Content -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_b\memory\.dream_cursor" -Value "0"
```

- [ ] **Step 2: Create dream.py**

```python
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
Return your findings as a bullet-point list prefixed with the current date.
Each bullet should be a single clear fact or decision.
Example:
### 2026-05-02 Dream Consolidation
- Decided to use Rust for the core engine due to performance requirements
- Learned that DeepSeek API requires reasoning_content to be passed back
- Prefer sub_agent for complex multi-file changes over direct editing
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


def get_unprocessed_history(agent_id: str) -> list[dict]:
    """Read history entries after the cursor."""
    since = get_cursor(agent_id)
    history_path = _agent_memory_dir(agent_id, "history.jsonl")
    if not os.path.exists(history_path):
        return []

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

    # All entries after cursor
    unprocessed = entries[since:]
    return unprocessed, len(entries)


def run_dream(agent_id: str, agent_name: str, llm_client=None) -> str:
    """Execute the Dream process: analyze history, update MEMORY.md."""
    from llm import LLMClient

    llm = llm_client or LLMClient()
    unprocessed, total_entries = get_unprocessed_history(agent_id)

    if not unprocessed:
        return "No new history entries to process."

    # Format history for LLM
    history_text = ""
    for i, entry in enumerate(unprocessed):
        history_text += f"\n### Entry {i+1}\n"
        history_text += f"Task: {entry.get('prompt', '?')[:300]}\n"
        history_text += f"Result: {entry.get('response_summary', '?')[:300]}\n"
        history_text += f"Iterations: {entry.get('iterations', '?')}\n"

    # Call LLM
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

    # Append findings to MEMORY.md
    mem_path = _agent_memory_dir(agent_id, "MEMORY.md")
    os.makedirs(os.path.dirname(mem_path), exist_ok=True)

    with open(mem_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n{content}\n")

    # Update cursor
    set_cursor(agent_id, total_entries)

    # Log how many entries were processed
    entry_count = len(unprocessed)
    return f"Dream processed {entry_count} history entries. Key findings added to long-term memory."


def _agent_memory_dir(agent_id: str, filename: str = "") -> str:
    """Get path to an agent's memory file."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", agent_id, "memory")
    if filename:
        return os.path.join(base, filename)
    return base
```

- [ ] **Step 3: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from dream import get_cursor, run_dream; print('cursor:', get_cursor('leader'))"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/dream.py agents/leader/memory/.dream_cursor agents/employee_a/memory/.dream_cursor agents/employee_b/memory/.dream_cursor
git commit -m "feat: add Dream processor with cursor-based history tracking"
```

---

### Task 2: Update DreamTool to trigger real Dream

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Update DreamTool.execute()**

Find `DreamTool` class, replace the execute method:

```python
    def execute(self, scope="recent", **kwargs) -> str:
        """Trigger the real Dream process."""
        from dream import run_dream
        try:
            result = run_dream(self.agent_id, self.agent_name)
            return result
        except Exception as e:
            return f"Dream failed: {e}"
```

- [ ] **Step 2: Update DreamTool.__init__ to accept agent_name**

```python
    def __init__(self, agent_id: str = "", agent_name: str = "Agent"):
        super().__init__()
        self.agent_id = agent_id
        self.agent_name = agent_name
```

- [ ] **Step 3: Update create_default_registry**

```python
    registry.register(DreamTool(agent_id=agent_id, agent_name=agent_name))
```

But we need to add `agent_name` parameter. Update the registry function to accept it:

```python
def create_default_registry(agent_runtime_path: str = "", scene_id: str = "default", agent_id: str = "", agent_name: str = "Agent") -> ToolRegistry:
```

And pass it:
```python
    registry.register(DreamTool(agent_id=agent_id, agent_name=agent_name))
```

- [ ] **Step 4: Build and test**

```bash
cargo build
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: DreamTool triggers real Dream LLM processing"
```

---

### Task 3: Auto-Dream + wire agent_name

**Files:**
- Modify: `py-agent/agent_loop.py`
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: Add auto-Dream to agent_loop.py**

In `run()`, after `append_history(...)`, add:

```python
        # Auto-Dream: process after every 3 history entries
        auto_dream(self.agent_id, self.agent_name, self.llm)
```

Add the function:

```python
def auto_dream(agent_id: str, agent_name: str, llm) -> None:
    """Auto-trigger Dream after every 3 unprocessed entries."""
    from dream import get_unprocessed_history, run_dream
    unprocessed, _ = get_unprocessed_history(agent_id)
    if len(unprocessed) >= 3:
        try:
            run_dream(agent_id, agent_name, llm_client=llm)
        except Exception:
            pass
```

- [ ] **Step 2: Wire agent_name in agent_runtime.py**

Update the lazy init block to pass `agent_name`:

```python
                tools = create_default_registry(
                    agent_runtime_path=agent_runtime_path,
                    scene_id=current_scene,
                    agent_id=agent_id,
                    agent_name=IDENTITY.get("name") or "Agent",
                )
```

- [ ] **Step 3: Build and run**

```bash
cargo build
```

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
cargo run
```

- [ ] **Step 4: Check results**

```powershell
Get-Content "C:\Users\12991\Desktop\Cococlaw\agents\leader\memory\MEMORY.md"
Get-Content "C:\Users\12991\Desktop\Cococlaw\agents\leader\memory\.dream_cursor"
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/agent_loop.py py-agent/agent_runtime.py
git commit -m "feat: auto-Dream after 3 history entries, wire agent_name"
```

---

## Summary

After this phase:
- ✅ Dream processor module (dream.py) with LLM-based history analysis
- ✅ `.dream_cursor` tracks processed entries (nanobot cursor pattern)
- ✅ `dream` tool triggers real LLM consolidation
- ✅ Auto-Dream every 3 history entries
- ✅ MEMORY.md updated with structured findings
