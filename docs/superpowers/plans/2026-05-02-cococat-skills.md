# Skill Tag System Implementation Plan

**Goal:** Complete the skill tag system — `public` (all agents), `private` (per-agent), and `env` (per-scene, already done). Skills are defined in `skills/` directory, manifests control which agents get which skills.

---

### Task 1: Create skill definitions + manifests

**Files:**
- Create: `skills/public/communication.md`
- Create: `skills/public/file-ops.md`
- Create: `skills/private/strategy.md`
- Create: `agents/leader/skills/manifest.json`
- Create: `agents/employee_a/skills/manifest.json`
- Create: `agents/employee_b/skills/manifest.json`

- [ ] **Step 1: Create skills directory**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\skills\public" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\skills\private" | Out-Null
```

- [ ] **Step 2: Public skill — communication.md**

```markdown
# Skill: Communication

Effectively communicate with team members and external stakeholders.

## Guidelines
- Be clear and concise in all messages
- Use @mentions to direct messages to specific agents
- Confirm receipt when a task is assigned
- Report progress and blockers proactively
```

- [ ] **Step 3: Public skill — file-ops.md**

```markdown
# Skill: File Operations

Read, write, and search files in the workspace.

## Guidelines
- Use read_file for reading, write_file for writing
- Use glob_search to find files by pattern
- Use grep_search to find content within files
- Always create parent directories when writing new files
```

- [ ] **Step 4: Private skill — strategy.md** (only leader has this)

```markdown
# Skill: Strategy

High-level planning and team coordination.

## Guidelines
- Assess team workload before assigning tasks
- Prioritize tasks based on team goals
- Use dispatch_task to delegate work to employees
- Maintain the schedule.json to track team assignments
```

- [ ] **Step 5: Agent manifests**

`agents/leader/skills/manifest.json`:
```json
{
  "public": ["communication", "file-ops"],
  "private": ["strategy"]
}
```

`agents/employee_a/skills/manifest.json`:
```json
{
  "public": ["communication", "file-ops"],
  "private": []
}
```

`agents/employee_b/skills/manifest.json`:
```json
{
  "public": ["communication", "file-ops"],
  "private": []
}
```

- [ ] **Step 6: Commit**

```bash
git add skills/ agents/leader/skills/ agents/employee_a/skills/ agents/employee_b/skills/
git commit -m "feat: add skill definitions and agent manifests (public/private)"
```

---

### Task 2: Load skills from all three sources

**Files:**
- Modify: `py-agent/context.py`

- [ ] **Step 1: Add load_agent_skills()**

```python
def load_agent_skills(agent_id: str) -> str:
    """Load public + private skills for an agent from its manifest."""
    import os as _os
    base = _os.path.dirname(_os.path.abspath(__file__))
    manifest_path = _os.path.join(base, "..", "agents", agent_id, "skills", "manifest.json")
    if not _os.path.exists(manifest_path):
        return ""

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return ""

    public_skills = manifest.get("public", [])
    private_skills = manifest.get("private", [])
    all_skill_names = public_skills + private_skills

    parts = []
    for skill_name in all_skill_names:
        # Check public dir first, then private dir
        for subdir in ["public", "private"]:
            skill_path = _os.path.join(base, "..", "skills", subdir, f"{skill_name}.md")
            if _os.path.exists(skill_path):
                try:
                    with open(skill_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    if content:
                        parts.append(content)
                except Exception:
                    pass
                break  # Found in this subdir

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)
```

- [ ] **Step 2: Update SYSTEM_PROMPT_TEMPLATE**

The template already has `{env_skills}`. Add `{agent_skills}` before it:

```python
## Active Skills
{agent_skills}

## Scene Skills
{env_skills}
```

- [ ] **Step 3: Update build_system_prompt**

Add `agent_skills` parameter:

```python
def build_system_prompt(
    ...
    agent_skills: str = "",
    env_skills: str = "",
) -> str:
```

And in the template format:
```python
        agent_skills=agent_skills or "(No specific skills assigned)",
        env_skills=env_skills or "(No special skills for this scene)",
```

- [ ] **Step 4: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from context import load_agent_skills; s=load_agent_skills('leader'); print('leader skills:', 'strategy' in s)"
python -c "import sys; sys.path.insert(0,'py-agent'); from context import load_agent_skills; s=load_agent_skills('employee_a'); print('employee_a skills:', len(s) > 0)"
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/context.py
git commit -m "feat: load public/private skills from agent manifest"
```

---

### Task 3: Wire through AgentLoop

**Files:**
- Modify: `py-agent/agent_loop.py`
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: Update AgentLoop run()**

In `run()`, after loading agent_memory, also load agent_skills:

```python
        agent_memory = load_agent_memory(self.agent_id)
        agent_skills = load_agent_skills(self.agent_id)
```

Pass to build_system_prompt:
```python
        system_prompt = build_system_prompt(
            ...
            agent_skills=agent_skills,
            env_skills=self.scene_skills,
        )
```

- [ ] **Step 2: Update agent_loop.py imports**

Add `from context import load_agent_memory, load_agent_skills` (or add `load_agent_skills` to existing import).

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

- [ ] **Step 4: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: inject agent skills (public+private) into system prompt"
```
