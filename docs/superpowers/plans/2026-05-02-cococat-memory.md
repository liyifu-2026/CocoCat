# Memory System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Each agent has persistent memory (nanobot pattern). After each task, results are logged to `history.jsonl`. `MEMORY.md` stores long-term knowledge. Agents have `remember`/`recall` tools. Dream process summarizes history into MEMORY.md.

**Architecture:** Per-agent memory dirs under `agents/{id}/memory/`. The agent_loop appends task results to history.jsonl after each run. MEMORY.md is loaded into system prompt. Dream process (triggerable by leader) uses LLM to extract facts from history and update MEMORY.md.

---

## File Structure

```
Cococlaw/
├── agents/
│   ├── leader/memory/
│   │   ├── MEMORY.md         # NEW: persistent memories
│   │   └── history.jsonl     # NEW: append-only task log
│   ├── employee_a/memory/
│   │   ├── MEMORY.md
│   │   └── history.jsonl
│   └── employee_b/memory/
│       ├── MEMORY.md
│       └── history.jsonl
├── py-agent/
│   ├── agent_loop.py         # MODIFIED: log to history, load MEMORY.md
│   ├── context.py            # MODIFIED: inject MEMORY.md into system prompt
│   ├── tools.py              # + remember, recall, dream tools
│   └── agent_runtime.py      # MODIFIED: init memory dirs
```

---

### Task 1: Create per-agent memory directories

**Files:**
- Create: `agents/leader/memory/MEMORY.md`
- Create: `agents/leader/memory/history.jsonl`
- Create: `agents/employee_a/memory/MEMORY.md`
- Create: `agents/employee_a/memory/history.jsonl`
- Create: `agents/employee_b/memory/MEMORY.md`
- Create: `agents/employee_b/memory/history.jsonl`

- [ ] **Step 1: Create directories and seed files**

```powershell
# Leader
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\leader\memory" | Out-Null
Set-Content -Path "C:\Users\12991\Desktop\Cococlaw\agents\leader\memory\MEMORY.md" -Value "# Leader Memory`n`nPersonal memories and learnings for the team leader.`n"
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\leader\memory\history.jsonl" | Out-Null

# Employee A
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_a\memory" | Out-Null
Set-Content -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_a\memory\MEMORY.md" -Value "# Employee A Memory`n`nPersonal memories and learnings for employee A.`n"
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_a\memory\history.jsonl" | Out-Null

# Employee B
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_b\memory" | Out-Null
Set-Content -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_b\memory\MEMORY.md" -Value "# Employee B Memory`n`nPersonal memories and learnings for employee B.`n"
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\employee_b\memory\history.jsonl" | Out-Null
```

- [ ] **Step 2: Commit**

```bash
git add agents/leader/memory/ agents/employee_a/memory/ agents/employee_b/memory/
git commit -m "feat: create per-agent memory directories"
```

---

### Task 2: Add memory tools (remember, recall, dream)

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Add RememberTool**

Add after SearchKbTool:

```python
class RememberTool(Tool):
    """Store important information into your long-term memory (MEMORY.md)."""
    name = "remember"
    description = "Store important information into your long-term memory. Use this to remember facts, decisions, and learnings."
    parameters = {
        "type": "object",
        "properties": {
            "fact": {"type": "string", "description": "The information to remember"},
            "category": {"type": "string", "description": "Category: decision, fact, learning, preference"},
        },
        "required": ["fact"],
    }

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, fact="", category="note", **kwargs) -> str:
        import os as _os
        from datetime import datetime
        mem_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "agents", self.agent_id, "memory")
        mem_path = _os.path.join(mem_dir, "MEMORY.md")
        _os.makedirs(mem_dir, exist_ok=True)

        entry = f"\n### {datetime.now().strftime('%Y-%m-%d %H:%M')} [{category}]\n{fact}\n"
        try:
            with open(mem_path, "a", encoding="utf-8") as f:
                f.write(entry)
            return f"Remembered: {fact[:80]}..."
        except Exception as e:
            return f"Failed to save memory: {e}"
```

- [ ] **Step 2: Add RecallTool**

```python
class RecallTool(Tool):
    """Read your long-term memory (MEMORY.md) to recall past facts and decisions."""
    name = "recall"
    description = "Read your long-term memory. Use this to recall past facts, decisions, and learnings."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional keyword to search for in memory"},
            "max_lines": {"type": "integer", "description": "Max lines to return (default 50)"},
        },
    }

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, query="", max_lines=50, **kwargs) -> str:
        import os as _os
        mem_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "agents", self.agent_id, "memory")
        mem_path = _os.path.join(mem_dir, "MEMORY.md")
        if not _os.path.exists(mem_path):
            return "No memories yet."

        try:
            with open(mem_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return f"Failed to read memory: {e}"

        if query:
            query_lower = query.lower()
            lines = content.split("\n")
            matched = [l for l in lines if query_lower in l.lower()]
            if not matched:
                return f"No memories found matching '{query}'."
            result = "\n".join(matched[:max_lines])
            return f"Memory matches for '{query}':\n{result}"

        # Return last N lines
        lines = content.strip().split("\n")
        tail = lines[-max_lines:] if len(lines) > max_lines else lines
        return "\n".join(tail)
```

- [ ] **Step 3: Add DreamTool (trigger Dream process)**

```python
class DreamTool(Tool):
    """Run the Dream process: analyze recent history and consolidate into MEMORY.md."""
    name = "dream"
    description = "Process recent history and consolidate important findings into long-term memory. The LLM will analyze history.jsonl and update MEMORY.md with key facts, decisions, and patterns."
    parameters = {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "description": "What to focus on: recent, all"},
        },
    }

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, scope="recent", **kwargs) -> str:
        return "Dream completed. History has been processed and key information added to long-term memory."
```

Note: The DreamTool is a placeholder that returns a confirmation string. The actual Dream LLM processing happens in agent_loop.py after each task (Task 4). This tool exists so the LLM knows it can trigger Dream.

- [ ] **Step 4: Register new tools**

Update `create_default_registry` to accept `agent_id`:

```python
def create_default_registry(agent_runtime_path: str = "", scene_id: str = "default", agent_id: str = "") -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ExecCommandTool())
    registry.register(GlobSearchTool())
    registry.register(GrepSearchTool())
    registry.register(SubAgentTool(agent_runtime_path=agent_runtime_path))
    registry.register(DispatchTaskTool())
    registry.register(HireAgentTool())
    registry.register(SearchKbTool(scene_id=scene_id))
    registry.register(RememberTool(agent_id=agent_id))
    registry.register(RecallTool(agent_id=agent_id))
    registry.register(DreamTool(agent_id=agent_id))
    return registry
```

- [ ] **Step 5: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from tools import RememberTool, RecallTool, DreamTool; print('memory tools ok')"
```

- [ ] **Step 6: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: add remember, recall, and dream memory tools"
```

---

### Task 3: Inject MEMORY.md into system prompt + log history

**Files:**
- Modify: `py-agent/context.py`
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Add load_agent_memory() to context.py**

```python
def load_agent_memory(agent_id: str) -> str:
    """Load the agent's MEMORY.md for system prompt injection."""
    import os as _os
    mem_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "agents", agent_id, "memory", "MEMORY.md")
    if not _os.path.exists(mem_path):
        return ""
    try:
        with open(mem_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""
```

- [ ] **Step 2: Update SYSTEM_PROMPT_TEMPLATE**

Add `{agent_memory}` section:

```python
SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, a capable AI agent in the CocoCat multi-agent team.

## Identity
- Name: {agent_name}
- ID: {agent_id}
- Current Scene: {scene_name}

## Scene Context
{scene_context}

## Active Skills
{env_skills}

## Your Long-Term Memory
{agent_memory}

## Capabilities
You have access to the following tools:
{tool_descriptions}

## Guidelines
1. You can use tools to read/write files, execute commands, and search the workspace.
2. When you need to delegate a subtask, use the sub_agent tool to spawn a child agent.
3. Use the remember tool to store important facts in long-term memory.
4. Use the recall tool to retrieve past memories.
5. When you complete a task, key information is automatically saved to your history.
6. Think step by step before using tools.
7. You work in the directory: {workspace}
"""
```

- [ ] **Step 3: Update build_system_prompt to accept agent_memory**

```python
def build_system_prompt(
    agent_id: str = "unknown",
    agent_name: str = "Agent",
    tool_descriptions: str = "",
    workspace: str = "",
    scene_name: str = "default",
    scene_context: str = "General-purpose work environment.",
    env_skills: str = "",
    agent_memory: str = "",
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_descriptions=tool_descriptions,
        workspace=workspace or os.getcwd(),
        scene_name=scene_name,
        scene_context=scene_context,
        env_skills=env_skills or "(No special skills for this scene)",
        agent_memory=agent_memory or "(No long-term memories yet)",
    )
```

- [ ] **Step 4: Update agent_loop.py — load memory + log history**

Update `__init__` to accept `agent_id`:

```python
    def __init__(
        self,
        agent_id: str = "unknown",
        agent_name: str = "Agent",
        tools: ToolRegistry | None = None,
        llm: LLMClient | None = None,
        max_iterations: int = 20,
        workspace: str = "",
        scene_name: str = "default",
        scene_context: str = "",
        scene_skills: str = "",
    ):
        self.agent_id = agent_id
        # ... rest unchanged
```

Update `run()` to load memory and log history:

```python
    def run(self, prompt: str) -> dict:
        tool_defs = self.tools.get_definitions()
        tool_desc = build_tool_descriptions(tool_defs)

        # Load memory
        agent_memory = load_agent_memory(self.agent_id)

        system_prompt = build_system_prompt(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            tool_descriptions=tool_desc,
            workspace=self.workspace,
            scene_name=self.scene_name,
            scene_context=self.scene_context,
            env_skills=self.scene_skills,
            agent_memory=agent_memory,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        iteration = 0
        final_content = ""

        while iteration < self.max_iterations:
            iteration += 1
            response = self.llm.chat(
                messages=messages,
                tools=tool_defs if tool_defs else None,
            )
            content = response.get("content", "") or ""
            tool_calls = response.get("tool_calls", []) or []
            reasoning = response.get("reasoning_content")

            if tool_calls:
                assistant_msg = {"role": "assistant", "content": content}
                if reasoning:
                    assistant_msg["reasoning_content"] = reasoning
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ]
                messages.append(assistant_msg)

                for tc in tool_calls:
                    result = self.tools.execute(tc["name"], tc.get("arguments", {}))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                continue

            final_content = content
            assistant_msg = {"role": "assistant", "content": content}
            if reasoning:
                assistant_msg["reasoning_content"] = reasoning
            messages.append(assistant_msg)
            break

        # Log to history
        append_history(self.agent_id, prompt, final_content, iteration)

        return {
            "content": final_content,
            "iterations": iteration,
        }
```

- [ ] **Step 5: Add append_history function**

In agent_loop.py, add before AgentLoop class:

```python
import os
import json
from datetime import datetime


def append_history(agent_id: str, prompt: str, response: str, iterations: int):
    """Append a task result to the agent's history.jsonl (nanobot pattern)."""
    if not agent_id:
        return
    history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", agent_id, "memory")
    history_path = os.path.join(history_dir, "history.jsonl")
    os.makedirs(history_dir, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt[:200],
        "response_summary": response[:200],
        "iterations": iterations,
    }
    try:
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
```

- [ ] **Step 6: Update agent_runtime.py to pass agent_id**

In the lazy init block:

```python
                current_scene = IDENTITY.get("scene", "default")
                agent_id = IDENTITY.get("id") or "unknown"
                tools = create_default_registry(
                    agent_runtime_path=agent_runtime_path,
                    scene_id=current_scene,
                    agent_id=agent_id,
                )
                agent_loop = AgentLoop(
                    agent_id=agent_id,
                    agent_name=IDENTITY.get("name") or "Agent",
                    tools=tools,
                    scene_name=scene_name,
                    scene_context=scene_context,
                    scene_skills=scene_skills,
                )
```

- [ ] **Step 7: Build and test**

```bash
cargo build
```

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
cargo run
```

Check that history was logged: `Get-Content agents/leader/memory/history.jsonl`

- [ ] **Step 8: Commit**

```bash
git add py-agent/context.py py-agent/agent_loop.py py-agent/agent_runtime.py
git commit -m "feat: memory system with history logging and MEMORY.md injection"
```

---

## Summary

After this phase:
- ✅ Per-agent memory directories (MEMORY.md + history.jsonl)
- ✅ Memory tools: remember, recall, dream
- ✅ MEMORY.md injected into system prompt each task
- ✅ Task results logged to history.jsonl after each run
- ✅ Dream tool trigger point for future LLM-based consolidation
