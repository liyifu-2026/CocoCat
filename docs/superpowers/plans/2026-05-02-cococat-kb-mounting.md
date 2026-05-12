# Knowledge Base Mounting Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Scenes mount knowledge bases. Agents working in a scene can search only the KBs mounted to that scene via a `search_kb` tool.

**Architecture:** KBs live in `knowledge/{kb_id}/wiki/` as markdown files. Scene config (`mounted_kbs.json`) lists which KBs are mounted. A `search_kb` tool on the Python side reads the scene's mounted_kbs and performs token-based grep search across the mounted KB files.

---

## File Structure

```
Cococlaw/
├── knowledge/
│   └── team-wiki/
│       ├── schema.md
│       └── wiki/
│           ├── entities/
│           │   └── cococat.md
│           └── concepts/
│               └── multi-agent-systems.md
├── scenes/
│   ├── default/
│   │   └── mounted_kbs.json     # MODIFIED
│   └── development/
│       └── mounted_kbs.json     # MODIFIED
├── py-agent/
│   ├── tools.py                 # + search_kb tool
│   └── context.py               # + load_mounted_kbs()
```

---

### Task 1: Create a sample KB + update scene mounts

**Files:**
- Create: `knowledge/team-wiki/schema.md`
- Create: `knowledge/team-wiki/wiki/entities/cococat.md`
- Create: `knowledge/team-wiki/wiki/concepts/multi-agent-systems.md`
- Modify: `scenes/development/mounted_kbs.json`

- [ ] **Step 1: Create directory structure**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\knowledge\team-wiki\wiki\entities" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\knowledge\team-wiki\wiki\concepts" | Out-Null
```

- [ ] **Step 2: Create schema.md**

```markdown
# Team Wiki Schema

A shared knowledge base for the CocoCat team.

## Page Types
- `entities/`: Named things (agents, tools, projects)
- `concepts/`: Ideas, patterns, techniques
```

- [ ] **Step 3: Create entities/cococat.md**

```markdown
---
type: entity
title: CocoCat
created: 2026-05-02
---

# CocoCat

CocoCat is a multi-agent team management system built with Rust + Python.

## Architecture
- **Rust Core**: Agent process manager, message bus, JSON-RPC transport
- **Python Agents**: LLM-driven agents with ReAct loop, tools, sub-agents
- **Scenes**: Work contexts with scene-specific memory and skills

## Key Components
- AgentRegistry: manages multiple agent processes
- AgentLoop: ReAct (LLM → tool → observe → repeat) execution engine
- Message Bus: routes messages between agents via dispatch queue
- Scene System: injects scene context and env-tagged skills
```

- [ ] **Step 4: Create concepts/multi-agent-systems.md**

```markdown
---
type: concept
title: Multi-Agent Systems
created: 2026-05-02
---

# Multi-Agent Systems

## Key Principles
1. **Single Responsibility**: Each agent has a clear role and set of skills
2. **Scene Isolation**: Agents work within scenes that provide relevant context
3. **Message Passing**: Agents communicate through a central message bus
4. **Human Oversight**: Team leader (组长) coordinates and assigns tasks

## Communication Patterns
- **Direct**: Agent A sends task to Agent B via dispatch_task tool
- **Broadcast**: System messages to all agents via chat log
- **Hierarchical**: Leader delegates to employees, employees report back

## Skill Tags
- `public`: All agents must learn
- `private`: Specific agent masters
- `env`: Scene provides automatically
```

- [ ] **Step 5: Mount team-wiki to development scene**

Update `scenes/development/mounted_kbs.json`:

```json
{
  "mounted": ["team-wiki"],
  "search_mode": "token"
}
```

- [ ] **Step 6: Commit**

```bash
git add knowledge/ scenes/development/mounted_kbs.json
git commit -m "feat: add team-wiki KB and mount to development scene"
```

---

### Task 2: Add search_kb tool + KB context to system prompt

**Files:**
- Modify: `py-agent/tools.py`
- Modify: `py-agent/context.py`

- [ ] **Step 1: Add load_mounted_kbs() to context.py**

```python
def load_mounted_kbs(scene_id: str) -> list[str]:
    """Return list of KB IDs mounted to this scene."""
    import os as _os
    scene_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "scenes", scene_id)
    mount_path = _os.path.join(scene_dir, "mounted_kbs.json")
    if not _os.path.exists(mount_path):
        return []
    try:
        with open(mount_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("mounted", [])
    except Exception:
        return []
```

- [ ] **Step 2: Add SearchKbTool to tools.py**

Read current `C:\Users\12991\Desktop\Cococlaw\py-agent\tools.py`. Add after `HireAgentTool` class (before `ToolRegistry`):

```python
class SearchKbTool(Tool):
    """Search the knowledge bases mounted to your current scene."""
    name = "search_kb"
    description = "Search knowledge bases mounted to your current scene. Returns matching content from KB wiki pages."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (keywords or phrase)"},
            "max_results": {"type": "integer", "description": "Maximum results to return (default 5)"},
        },
        "required": ["query"],
    }

    def __init__(self, scene_id: str = "default"):
        super().__init__()
        self.scene_id = scene_id

    def execute(self, query="", max_results=5, **kwargs) -> str:
        import os as _os
        import re as _re

        # Load mounted KBs for this scene
        script_dir = _os.path.dirname(_os.path.abspath(__file__))
        mount_path = _os.path.join(script_dir, "..", "scenes", self.scene_id, "mounted_kbs.json")

        if not _os.path.exists(mount_path):
            return "No knowledge bases mounted for this scene."

        try:
            with open(mount_path, "r", encoding="utf-8") as f:
                mount_data = json.load(f)
        except Exception as e:
            return f"Failed to load mounted KBs: {e}"

        mounted = mount_data.get("mounted", [])
        if not mounted:
            return "No knowledge bases mounted for this scene."

        # Search each mounted KB
        kb_base = _os.path.join(script_dir, "..", "knowledge")
        results = []

        for kb_id in mounted:
            wiki_dir = _os.path.join(kb_base, kb_id, "wiki")
            if not _os.path.isdir(wiki_dir):
                continue

            for root, dirs, files in _os.walk(wiki_dir):
                for f in files:
                    if not f.endswith(".md"):
                        continue
                    fp = _os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                            content = fh.read()
                    except Exception:
                        continue

                    # Simple token search (case-insensitive)
                    query_lower = query.lower()
                    if query_lower in content.lower():
                        # Extract context around match
                        lines = content.split("\n")
                        matched_lines = []
                        for i, line in enumerate(lines):
                            if query_lower in line.lower():
                                start = max(0, i - 1)
                                end = min(len(lines), i + 3)
                                snippet = "\n".join(lines[start:end])
                                rel_path = _os.path.relpath(fp, kb_base)
                                matched_lines.append(f"[{rel_path}:{i+1}]\n{snippet}")
                        if matched_lines:
                            results.extend(matched_lines)

        if not results:
            return f"No matches found for '{query}' in mounted KBs."

        # Deduplicate and limit
        seen = set()
        unique = []
        for r in results:
            if r not in seen:
                seen.add(r)
                unique.append(r)

        top = unique[:max_results]
        output = f"Found {len(unique)} matches (showing {len(top)}):\n\n"
        output += "\n\n---\n\n".join(top)
        return output
```

Register in `create_default_registry` — change it to accept scene_id:

```python
def create_default_registry(agent_runtime_path: str = "", scene_id: str = "default") -> ToolRegistry:
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
    return registry
```

- [ ] **Step 3: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from context import load_mounted_kbs; print('Mounted KBs:', load_mounted_kbs('development'))"
python -c "import sys; sys.path.insert(0,'py-agent'); from tools import SearchKbTool; t = SearchKbTool(scene_id='development'); print(t.execute('CocoCat'))"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/tools.py py-agent/context.py
git commit -m "feat: add search_kb tool and scene KB mounting"
```

---

### Task 3: Wire scene_id through agent init

**Files:**
- Modify: `py-agent/agent_loop.py`
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: Pass scene_id to create_default_registry in agent_runtime.py**

Update the lazy init block:

```python
                current_scene = IDENTITY.get("scene", "default")
                tools = create_default_registry(
                    agent_runtime_path=agent_runtime_path,
                    scene_id=current_scene,
                )
```

- [ ] **Step 2: Build and run**

```bash
cargo build
cargo run
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_runtime.py
git commit -m "feat: pass scene_id to tool registry for KB search"
```

---

### Task 4: End-to-end KB search demo

- [ ] **Step 1: Run and verify KB search**

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
cargo run
```

Expected: Employee_b (default scene, no KBs mounted) can't search. Leader (development scene) has search_kb tool and can query team-wiki.

- [ ] **Step 2: Commit any final fixes**

```bash
git add -A
git commit -m "feat: KB mounting working end-to-end"
```

---

## Summary

After this phase:
- ✅ KB storage structure (knowledge/{kb_id}/wiki/)
- ✅ Sample KB with entity + concept pages
- ✅ Scene-mounted KBs (development → team-wiki)
- ✅ search_kb tool that searches only mounted KBs
- ✅ Different scenes have different KB access
