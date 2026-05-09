# Env-Tagged Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Skills declared in `scenes/{scene}/skills/manifest.json` (env-tagged) are automatically loaded from `.md` files and injected into the agent's system prompt when working in that scene.

**Architecture:** Each env skill is a markdown file in `scenes/{scene}/skills/{name}.md`. The `load_scene_context` function also loads the scene's env skills. They are added to the system prompt as an "Active Skills" section.

---

## File Structure

```
Cococlaw/
├── scenes/
│   └── development/
│       └── skills/
│           ├── manifest.json     # declares ["code_review", "prd_writing"]
│           ├── code_review.md    # NEW: skill definition
│           └── prd_writing.md    # NEW: skill definition
├── py-agent/
│   ├── context.py               # MODIFIED: load and inject env skills
│   └── agent_loop.py            # MODIFIED: pass scene skills to context
```

---

### Task 1: Create env skill markdown files

**Files:**
- Create: `scenes/development/skills/code_review.md`
- Create: `scenes/development/skills/prd_writing.md`

- [ ] **Step 1: Create code_review.md**

```markdown
# Skill: Code Review

Review code changes for quality, correctness, and style.

## Process
1. Read the changed files and understand the context
2. Check for: logic errors, edge cases, security issues, style violations
3. Provide constructive feedback with specific line references
4. Suggest improvements when applicable

## Guidelines
- Be specific: reference exact lines and logic
- Be constructive: explain why something is a problem
- Prioritize: critical bugs > correctness > style
```

- [ ] **Step 2: Create prd_writing.md**

```markdown
# Skill: PRD Writing

Write Product Requirements Documents for new features.

## Structure
1. **Problem Statement**: What problem are we solving?
2. **Goals**: What success looks like (measurable)
3. **Scope**: What's in and out of scope
4. **Technical Approach**: High-level implementation strategy
5. **Open Questions**: Decisions that need input

## Guidelines
- Write for both technical and non-technical readers
- Include acceptance criteria for each requirement
- Link to relevant context (existing code, discussions)
```

- [ ] **Step 3: Commit**

```bash
git add scenes/development/skills/code_review.md scenes/development/skills/prd_writing.md
git commit -m "feat: add env skill definitions for development scene"
```

---

### Task 2: Load env skills in context.py

**Files:**
- Modify: `py-agent/context.py`

- [ ] **Step 1: Add load_env_skills function**

Add after `load_scene_context`:

```python
def load_env_skills(scene_id: str) -> str:
    """Load env-tagged skills from scenes/{scene_id}/skills/manifest.json and their .md files."""
    import os as _os
    scene_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "scenes", scene_id)
    manifest_path = _os.path.join(scene_dir, "skills", "manifest.json")

    if not _os.path.exists(manifest_path):
        return ""

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return ""

    env_skills = manifest.get("env_skills", [])
    if not env_skills:
        return ""

    parts = []
    for skill_name in env_skills:
        skill_path = _os.path.join(scene_dir, "skills", f"{skill_name}.md")
        if _os.path.exists(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                parts.append(content)

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)
```

- [ ] **Step 2: Update SYSTEM_PROMPT_TEMPLATE**

Add `{env_skills}` section:

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

## Capabilities
You have access to the following tools:
{tool_descriptions}

## Guidelines
1. You can use tools to read/write files, execute commands, and search the workspace.
2. When you need to delegate a subtask, use the sub_agent tool to spawn a child agent.
3. Think step by step before using tools.
4. When you have completed the task, provide a clear summary of what was done.
5. You work in the directory: {workspace}
"""
```

- [ ] **Step 3: Update build_system_prompt to accept env_skills**

```python
def build_system_prompt(
    agent_id: str = "unknown",
    agent_name: str = "Agent",
    tool_descriptions: str = "",
    workspace: str = "",
    scene_name: str = "default",
    scene_context: str = "General-purpose work environment.",
    env_skills: str = "",
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_descriptions=tool_descriptions,
        workspace=workspace or os.getcwd(),
        scene_name=scene_name,
        scene_context=scene_context,
        env_skills=env_skills or "(No special skills for this scene)",
    )
```

- [ ] **Step 4: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from context import load_env_skills; skills = load_env_skills('development'); print('Skills loaded:', len(skills) > 0); print(skills[:100])"
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/context.py
git commit -m "feat: load env-tagged skills from scene manifest"
```

---

### Task 3: Pass env skills through AgentLoop

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Update AgentLoop.__init__**

Add `scene_skills` parameter:

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
        self.agent_name = agent_name
        self.tools = tools or create_default_registry()
        self.llm = llm or LLMClient()
        self.max_iterations = max_iterations
        self.workspace = workspace
        self.scene_name = scene_name
        self.scene_context = scene_context
        self.scene_skills = scene_skills
```

- [ ] **Step 2: Update run() to pass scene_skills**

```python
        system_prompt = build_system_prompt(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            tool_descriptions=tool_desc,
            workspace=self.workspace,
            scene_name=self.scene_name,
            scene_context=self.scene_context,
            env_skills=self.scene_skills,
        )
```

- [ ] **Step 3: Build and test**

```bash
cargo build
python -c "import sys; sys.path.insert(0,'py-agent'); from agent_loop import AgentLoop; a = AgentLoop(scene_name='Development Scene', scene_skills='code_review skill loaded'); print('AgentLoop scene_skills:', bool(a.scene_skills))"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/agent_loop.py
git commit -m "feat: pass scene env skills through AgentLoop"
```

---

### Task 4: Wire env skills in agent_runtime.py

**Files:**
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: Update lazy AgentLoop init to load env skills**

In agent_runtime.py, find the lazy init block and update it:

```python
            if request.get("method") == "task" and agent_loop is None:
                from agent_loop import AgentLoop
                from tools import create_default_registry
                from context import load_scene_context, load_env_skills

                script_dir = os.path.dirname(os.path.abspath(__file__))
                agent_runtime_path = os.path.join(script_dir, "agent_runtime.py")

                scene_name, scene_context = load_scene_context(IDENTITY.get("scene", "default"))
                scene_skills = load_env_skills(IDENTITY.get("scene", "default"))

                tools = create_default_registry(agent_runtime_path=agent_runtime_path)
                agent_loop = AgentLoop(
                    agent_id=IDENTITY["id"] or "unknown",
                    agent_name=IDENTITY["name"] or "Agent",
                    tools=tools,
                    scene_name=scene_name,
                    scene_context=scene_context,
                    scene_skills=scene_skills,
                )
```

- [ ] **Step 2: Commit**

```bash
git add py-agent/agent_runtime.py
git commit -m "feat: wire env skills into agent runtime"
```

---

### Task 5: Verify end-to-end

**Files:**
- No changes needed — just run

- [ ] **Step 1: Build and run**

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
cargo build
cargo run
```

Expected: Leader (development scene) has code_review and prd_writing skills in its system prompt. Employee_b (default scene) has no env skills.

- [ ] **Step 2: Commit any final fixes**

```bash
git add -A
git commit -m "feat: env-tagged skills working end-to-end"
```

---

## Summary

After this phase:
- ✅ Env skill definitions (code_review.md, prd_writing.md)
- ✅ Scene manifest declares which env skills are active
- ✅ load_env_skills() reads manifest + skill .md files
- ✅ System prompt includes Active Skills section
- ✅ Different scenes have different active skills
