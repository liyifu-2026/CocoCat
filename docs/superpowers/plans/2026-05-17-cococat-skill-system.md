# CocoCat Skill System Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flatten skill files into a single `skills/` directory, unify loader API, add frontmatter tags + `as_tool` support, wire skills into agent profile and scene config.

**Architecture:** All skill `.md` files live in `skills/`. `cococat/skills.py` exposes `load_skill(name)`, `resolve_skills(names)`, `skills_to_prompt(skills)`, `skills_to_tools(skills)`. Agent loads skills from `profile.yaml`; scene binding merges agent + scene skill lists. Deleted skills are silently skipped with a log warning.

**Tech Stack:** Python 3.12+, PyYAML, pytest

---

## File Structure

```
skills/                          # ← unified skill files
  code_review.md
  prd_writing.md
  communication.md
  file-ops.md
  strategy.md
  knowledge-ingestion.md

cococat/skills.py                # ← rewritten
cococat/prompt.py                # ← modified: new skills_prompt param
cococat/profile.py               # ← modified: load_agent_profile returns skills list
cococat/core/agent.py            # ← modified: load + merge skills on init + bind
cococat/routes/skills.py         # ← modified: new paths
cococat/scene/config.py          # ← unchanged (already has skills field)
cococat/scene/config.py          # ← unchanged

tests/cococat/test_skills.py     # ← rewritten

agents/leader/profile.yaml       # ← new
agents/employee_a/profile.yaml   # ← new
agents/employee_b/profile.yaml   # ← new

scenes/development/scene.yaml    # ← new
scenes/customer-service/scene.yaml # ← new
scenes/default/scene.yaml        # ← new
```

---

### Task 1: Create unified skill files

**Files:**
- Create: `skills/code_review.md`
- Create: `skills/prd_writing.md`
- Create: `skills/communication.md`
- Create: `skills/file-ops.md`
- Create: `skills/strategy.md`
- Create: `skills/knowledge-ingestion.md`

- [ ] **Step 1: Create skills/code_review.md**

```markdown
---
name: Code Review
description: Review code for quality, correctness, and style
tags: [development, review, qa]
---

# Code Review Skill

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

- [ ] **Step 2: Create skills/prd_writing.md**

```markdown
---
name: PRD Writing
description: Write Product Requirements Documents for new features
tags: [development, planning, documentation]
---

# PRD Writing Skill

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

- [ ] **Step 3: Create skills/communication.md**

```markdown
---
name: Communication
description: Effectively communicate with team members and stakeholders
tags: [communication, team]
---

# Communication Skill

Effectively communicate with team members and external stakeholders.

## Guidelines
- Be clear and concise in all messages
- Use @mentions to direct messages to specific agents
- Confirm receipt when a task is assigned
- Report progress and blockers proactively
```

- [ ] **Step 4: Create skills/file-ops.md**

```markdown
---
name: File Operations
description: Read, write, and search files in the workspace
tags: [files, workspace]
---

# File Operations Skill

Read, write, and search files in the workspace.

## Guidelines
- Use read_file for reading, write_file for writing
- Use glob_search to find files by pattern
- Use grep_search to find content within files
- Always create parent directories when writing new files
```

- [ ] **Step 5: Create skills/strategy.md**

```markdown
---
name: Strategy
description: High-level planning and team coordination
tags: [planning, coordination, leadership]
---

# Strategy Skill

High-level planning and team coordination.

## Guidelines
- Assess team workload before assigning tasks
- Prioritize tasks based on team goals
- Use dispatch_task to delegate work to employees
- Maintain the schedule.json to track team assignments
```

- [ ] **Step 6: Create skills/knowledge-ingestion.md**

```markdown
---
name: Knowledge Ingestion
description: Ingest source material into knowledge bases
tags: [knowledge-base, ingestion]
as_tool: true
---

# Knowledge Ingestion Skill

You are a knowledge base maintainer. When a user gives you source material, follow this process.

## 1. Material Analysis
- Identify the type: document, code, conversation log, image description
- Extract key entities (named things, components, people, tools)
- Extract key concepts (ideas, patterns, techniques, architectures)
- Determine overlap with existing wiki: use `search_kb` to check

## 2. Injection Strategy
- New entity -> create `wiki/entities/{slug}.md` using `write_wiki`
- New concept -> create `wiki/concepts/{slug}.md` using `write_wiki`
- Existing page needs updating -> merge new info using `write_wiki` (it overwrites)
- Use `[[slug]]` wikilinks to cross-reference related pages
- Each page must have YAML frontmatter: type, title, created, summary, sources, tags

## 3. Frontmatter Convention
```yaml
---
type: entity          # or concept
title: Display Name
created: 2026-05-16
summary: One-line description
sources:
  - source-filename.pdf
tags:
  - category
  - keyword
related:
  - other-slug
---
```

## 4. Quality Control
- Run `search_kb` to verify no duplicate exists before writing
- After writing, verify the page reads correctly with `read_wiki`
- Ensure all `[[wikilinks]]` point to existing pages or create the target pages
- Update relevant pages that should link back to the new page

## 5. Batch Processing
If the user uploads a file, you may use `call_worker` to run the ingest pipeline:
```
call_worker(task="Run ingest pipeline for FILE in KB KBNAME")
```
The worker will execute the two-phase LLM ingestion and write wiki pages.

For complex materials, process them yourself step by step using the tools above.
```

- [ ] **Step 7: Commit**

```bash
git add skills/
git commit -m "feat: create unified skill files with frontmatter metadata"
```

---

### Task 2: Rewrite skills.py — core loader

**Files:**
- Modify: `cococat/skills.py`
- Test: `tests/cococat/test_skills.py`

- [ ] **Step 1: Write the failing test for load_skill**

In `tests/cococat/test_skills.py`, replace all existing test code:

```python
"""Tests for skills loader."""
import os
import tempfile
import pytest
from cococat.skills import load_skill, resolve_skills, skills_to_prompt, skills_to_tools


def test_load_skill_with_frontmatter():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(d)
        md = os.path.join(d, "code_review.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("---\nname: Code Review\ndescription: Review code\n"
                    "tags: [development, review]\nas_tool: true\n---\n\n# Review\nBody here.")

        skill = load_skill("code_review", skills_dir=d)
        assert skill is not None
        assert skill["id"] == "code_review"
        assert skill["name"] == "Code Review"
        assert skill["description"] == "Review code"
        assert skill["tags"] == ["development", "review"]
        assert skill["as_tool"] is True
        assert "Body here" in skill["body"]
        assert "---" not in skill["body"]


def test_load_skill_no_frontmatter():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(d)
        md = os.path.join(d, "hello.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("# Just a markdown file\nInstructions here.")

        skill = load_skill("hello", skills_dir=d)
        assert skill is not None
        assert skill["id"] == "hello"
        assert skill["name"] == "hello"
        assert "Instructions" in skill["description"]
        assert skill["tags"] == []
        assert skill["as_tool"] is False
        assert "# Just a markdown file" in skill["body"]


def test_load_skill_nonexistent():
    skill = load_skill("nonexistent", skills_dir="/tmp/nope")
    assert skill is None


def test_resolve_skills():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(d)
        with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: A\n---\n\n# A body")
        with open(os.path.join(d, "b.md"), "w", encoding="utf-8") as f:
            f.write("# B body")

        skills = resolve_skills(["a", "b", "missing"], skills_dir=d)
        assert len(skills) == 2
        ids = {s["id"] for s in skills}
        assert ids == {"a", "b"}


def test_resolve_skills_empty():
    skills = resolve_skills([], skills_dir="/tmp/nope")
    assert skills == []


def test_skills_to_prompt():
    skills = [
        {"id": "a", "name": "A", "description": "...", "tags": [], "as_tool": False, "body": "Skill A body\nLine 2"},
        {"id": "b", "name": "B", "description": "...", "tags": ["x"], "as_tool": False, "body": "Skill B body"},
    ]
    prompt = skills_to_prompt(skills)
    assert "## Active Skills" in prompt
    assert "### a" in prompt
    assert "Skill A body" in prompt
    assert "### b" in prompt
    assert "Skill B body" in prompt


def test_skills_to_prompt_empty():
    assert skills_to_prompt([]) == ""


def test_skills_to_tools():
    skills = [
        {"id": "a", "name": "A", "description": "Desc A", "tags": [], "as_tool": True, "body": "A body"},
        {"id": "b", "name": "B", "description": "Desc B", "tags": [], "as_tool": False, "body": "B body"},
        {"id": "c", "name": "C", "description": "Desc C", "tags": [], "as_tool": True, "body": "C body"},
    ]
    tools = skills_to_tools(skills)
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert names == {"a", "c"}
    assert "Desc A" in [t["description"] for t in tools]


def test_skills_to_tools_empty():
    assert skills_to_tools([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cococat/test_skills.py -v`
Expected: all tests FAIL with `ImportError` (new function names not yet defined).

- [ ] **Step 3: Rewrite cococat/skills.py**

```python
"""Skills loader — reads .md skill files from skills/ directory."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger("cococat.skills")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

MAX_PROMPT_PER_SKILL = 4000
MAX_TOOL_OUTPUT = 2000


def load_skill(name: str, skills_dir: str = "skills") -> dict[str, Any] | None:
    """Load a single skill from skills/{name}.md.

    Returns dict with keys: id, name, description, tags, as_tool, body.
    Returns None if file not found or unreadable.
    """
    path = os.path.join(skills_dir, f"{name}.md")
    if not os.path.exists(path):
        return None

    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return None

    display_name = name
    description = raw[:200].strip()
    tags: list[str] = []
    as_tool = False

    match = _FRONTMATTER_RE.match(raw)
    if match:
        try:
            import yaml
            fm = yaml.safe_load(match.group(1))
            if isinstance(fm, dict):
                display_name = fm.get("name", display_name)
                description = fm.get("description", description)
                tags = fm.get("tags") or []
                as_tool = bool(fm.get("as_tool", False))
        except Exception:
            pass
        body = raw[match.end():].strip()
    else:
        body = raw.strip()

    return {
        "id": name,
        "name": display_name,
        "description": description[:500],
        "tags": tags,
        "as_tool": as_tool,
        "body": body,
    }


def resolve_skills(names: list[str], skills_dir: str = "skills") -> list[dict[str, Any]]:
    """Load multiple skills by name. Missing skills are skipped with a log warning."""
    skills = []
    for name in names:
        s = load_skill(name, skills_dir)
        if s:
            skills.append(s)
        else:
            logger.warning("Skill '%s' not found in %s/", name, skills_dir)
    return skills


def skills_to_prompt(skills: list[dict[str, Any]]) -> str:
    """Convert skill list to a system prompt block."""
    if not skills:
        return ""

    lines = ["## Active Skills"]
    for s in skills:
        lines.append(f"\n### {s['id']}")
        body = s["body"]
        if len(body) > MAX_PROMPT_PER_SKILL:
            body = body[:MAX_PROMPT_PER_SKILL] + "\n[...truncated]"
        lines.append(body)

    return "\n".join(lines)


def skills_to_tools(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tool definitions for skills with as_tool == true."""
    tools = []
    for s in skills:
        if not s.get("as_tool"):
            continue
        body = s["body"]
        _body_ref = body  # captured for closure

        tools.append({
            "name": s["id"],
            "description": s["description"],
            "parameters": {
                "type": "object",
                "properties": {},
            },
            "execute": lambda p=None, ctx=None, b=_body_ref: b[:MAX_TOOL_OUTPUT],
        })
    return tools
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/cococat/test_skills.py -v`
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cococat/skills.py tests/cococat/test_skills.py
git commit -m "feat: rewrite skills loader with unified API (load/resolve/prompt/tools)"
```

---

### Task 3: Update profile.py — return skills from agent profile

**Files:**
- Modify: `cococat/profile.py`

- [ ] **Step 1: Update load_agent_profile to include skills**

Edit `cococat/profile.py`, change the function to also return the raw profile dict (which now contains `skills`):

No code changes needed for `load_agent_profile` — it already uses `profile.update(data)` which automatically captures any YAML key including `skills`.

- [ ] **Step 2: Add get_agent_skills helper**

Add to `cococat/profile.py` after `load_agent_system_prompt`:

```python
def get_agent_skills(agent_dir: str) -> list[str]:
    """Extract skill names from agent's profile.yaml."""
    if not agent_dir:
        return []
    profile = load_agent_profile(agent_dir)
    return profile.get("skills") or []
```

- [ ] **Step 3: Run existing tests to confirm no regression**

Run: `python -m pytest tests/cococat/ -v -k "profile or skill" 2>/dev/null || echo "no profile tests yet"`
Expected: no breakage.

- [ ] **Step 4: Commit**

```bash
git add cococat/profile.py
git commit -m "feat: add get_agent_skills from profile.yaml"
```

---

### Task 4: Create agent profile.yaml files

**Files:**
- Create: `agents/leader/profile.yaml`
- Create: `agents/employee_a/profile.yaml`
- Create: `agents/employee_b/profile.yaml`

- [ ] **Step 1: Create agents/leader/profile.yaml**

```yaml
name: Leader
role: resident
personality: Strategic and decisive team coordinator
skills:
  - communication
  - file-ops
  - strategy
```

- [ ] **Step 2: Create agents/employee_a/profile.yaml**

```yaml
name: Employee A
role: worker
skills:
  - communication
  - file-ops
```

- [ ] **Step 3: Create agents/employee_b/profile.yaml**

```yaml
name: Employee B
role: worker
skills:
  - communication
  - file-ops
```

- [ ] **Step 4: Commit**

```bash
git add agents/leader/profile.yaml agents/employee_a/profile.yaml agents/employee_b/profile.yaml
git commit -m "feat: add agent profile files with skills"
```

---

### Task 5: Create scene.yaml files

**Files:**
- Create: `scenes/development/scene.yaml`
- Create: `scenes/customer-service/scene.yaml`
- Create: `scenes/default/scene.yaml`

- [ ] **Step 1: Create scenes/development/scene.yaml**

```yaml
id: development
name: Development
context: |
  Software development work environment.

  ## Guidelines
  - Focus on code quality, testing, and documentation
  - Follow the team's coding standards
  - All code changes should be reviewed
  - Use sub_agent for complex multi-file changes

  ## Active Projects
  - CocoCat MVP: core agent system
  - Message bus integration
kbs:
  - team-wiki
skills:
  - code_review
  - prd_writing
roster:
  - leader
  - employee_a
```

- [ ] **Step 2: Create scenes/customer-service/scene.yaml**

```yaml
id: customer-service
name: Customer Service
context: |
  You are a professional customer service agent. Respond politely, patiently, and helpfully.

  ## Guidelines
  - Be professional and courteous at all times
  - Answer questions based on the knowledge base when available
  - If you don't know the answer, say so honestly
  - Escalate complex issues to a human if needed
  - Keep responses concise and clear
  - Remember user context from conversation history
kbs: []
skills:
  - communication
roster: []
```

- [ ] **Step 3: Create scenes/default/scene.yaml**

```yaml
id: default
name: Default
context: |
  General-purpose work environment for the CocoCat team.

  ## Guidelines
  - All team members are available for general tasks
  - Default tools are available to all agents
  - No special knowledge bases mounted
kbs: []
skills: []
roster: []
```

- [ ] **Step 4: Verify loads correctly**

Run:
```bash
python -c "
from cococat.scene.config import load_scene_config
for s in ['development', 'customer-service', 'default']:
    c = load_scene_config(s)
    print(f'{s}: id={c.id}, skills={c.skills}')
"
```
Expected: all three scenes load with correct skills.

- [ ] **Step 5: Commit**

```bash
git add scenes/development/scene.yaml scenes/customer-service/scene.yaml scenes/default/scene.yaml
git commit -m "feat: add scene.yaml config files with skills"
```

---

### Task 6: Update prompt.py — accept rendered skills prompt

**Files:**
- Modify: `cococat/prompt.py:209-212`

- [ ] **Step 1: Replace name-list skills with rendered skills prompt block**

In `cococat/prompt.py`, change lines 209-212 from:

```python
    if scene_skills:
        skills_text = "\n".join(f"- {s}" for s in scene_skills)
        parts.append(f"\n## Scene Skills\n{skills_text}")
```

To:

```python
    if scene_skills:
        parts.append(f"\n{scene_skills}")
```

(The caller now passes pre-rendered prompt text from `skills_to_prompt()`, not a list of names.)

- [ ] **Step 2: Verify no test breakage**

Run: `python -m pytest tests/cococat/ -v -k "prompt" 2>/dev/null || echo "no prompt tests"`
Expected: no existing prompt tests break.

- [ ] **Step 3: Commit**

```bash
git add cococat/prompt.py
git commit -m "refactor: prompt accepts pre-rendered skills text instead of name list"
```

---

### Task 7: Update agent.py — load skills from profile + merge on scene bind

**Files:**
- Modify: `cococat/core/agent.py:63-79` (init) and `cococat/core/agent.py:82-117` (bind_to_scene)

- [ ] **Step 1: Read current agent.py**

Already done during design phase.

- [ ] **Step 2: Update __init__ to load agent skills**

Replace agent.py lines 63-79 (the init's profile/memory/skills section) with:

```python
        memory_content, pinned = "", ""
        profile_text = ""
        self._agent_skill_names: list[str] = []
        if agent_dir:
            memory_content, pinned = load_memory_from_agent_dir(agent_dir)
            profile_text = load_agent_system_prompt(agent_dir)
            from cococat.profile import get_agent_skills
            self._agent_skill_names = get_agent_skills(agent_dir)

        # Load agent skills
        self._agent_skills = resolve_skills(self._agent_skill_names)
        agent_skills_prompt = skills_to_prompt(self._agent_skills)
        agent_skill_tools = skills_to_tools(self._agent_skills)

        self._base_tools = tools or create_core_tools()
        # Merge agent skill tools into base
        self._base_tools = list(self._base_tools) + agent_skill_tools
        self._scene_tools: list[dict] = []
        self._sandbox: Optional[PathSandbox] = None

        self._system_prompt = system_prompt or build_system_prompt(
            agent_profile=name + ("\n" + profile_text if profile_text else ""),
            memory_content=memory_content,
            pinned_facts=pinned,
            scene_skills=agent_skills_prompt,
            tools=self._base_tools,
            static_prefix=KB_AGENT_STATIC_PREFIX if id == "kb-agent" else None,
        )
        self._default_system_prompt = self._system_prompt
```

- [ ] **Step 3: Remove old import of load_scene_skills**

Replace line 12:
```python
from cococat.skills import load_scene_skills
```
With:
```python
from cococat.skills import resolve_skills, skills_to_prompt, skills_to_tools
```

- [ ] **Step 4: Update bind_to_scene to merge skills**

Replace lines 102-113 (the scene_config block) with:

```python
        if scene_config:
            # Merge agent skills + scene skills (union, de-duplicated)
            all_skill_names = list(dict.fromkeys(self._agent_skill_names + scene_config.skills))
            merged_skills = resolve_skills(all_skill_names)
            merged_prompt = skills_to_prompt(merged_skills)
            merged_tools = skills_to_tools(merged_skills)

            self._system_prompt = build_system_prompt(
                agent_profile=self.name,
                scene_context=scene_config.context,
                scene_kbs=scene_config.kbs,
                scene_skills=merged_prompt,
                tools=list(self._base_tools) + merged_tools,
            )
            self._scene_tools = merged_tools
            self._sandbox = PathSandbox(allowed_kbs=scene_config.kbs)
```

- [ ] **Step 5: Verify imports are complete**

Ensure `agent.py` has these imports at the top:
```python
from cococat.skills import resolve_skills, skills_to_prompt, skills_to_tools
```

- [ ] **Step 6: Run existing tests to verify no regression**

Run: `python -m pytest tests/cococat/ -v`
Expected: all existing tests pass.

- [ ] **Step 7: Commit**

```bash
git add cococat/core/agent.py
git commit -m "feat: load skills from profile, merge agent+scene skills on bind"
```

---

### Task 8: Update skills API routes

**Files:**
- Modify: `cococat/routes/skills.py`

- [ ] **Step 1: Rewrite routes/skills.py**

```python
"""Skills routes."""
import os
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel

from cococat.skills import load_skill, resolve_skills

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    content: str


@router.get("")
async def list_skills(request: Request, tag: str | None = Query(None)):
    """List all skills from skills/ directory. Optional tag filter."""
    skills_dir = "skills"
    result: list[dict] = []

    if not os.path.isdir(skills_dir):
        return {"skills": result}

    for fname in sorted(os.listdir(skills_dir)):
        if not fname.endswith(".md"):
            continue
        name = fname[:-3]
        s = load_skill(name)
        if not s:
            continue
        if tag and tag not in s.get("tags", []):
            continue
        result.append({
            "name": s["name"],
            "id": s["id"],
            "description": s["description"][:100],
            "tags": s.get("tags", []),
            "as_tool": s.get("as_tool", False),
        })

    return {"skills": result}


@router.get("/{skill_name}")
async def get_skill(skill_name: str):
    """Read a single skill's markdown content."""
    path = os.path.join("skills", f"{skill_name}.md")
    if not os.path.exists(path):
        return {"error": "not found"}, 404

    skill = load_skill(skill_name)
    if not skill:
        return {"error": "failed to load"}, 500

    return {
        "id": skill["id"],
        "name": skill["name"],
        "description": skill["description"],
        "tags": skill["tags"],
        "as_tool": skill["as_tool"],
        "body": skill["body"],
    }
```

- [ ] **Step 2: Verify routes import correctly**

Run:
```bash
python -c "from cococat.routes.skills import router; print('router OK')"
```
Expected: `router OK`

- [ ] **Step 3: Commit**

```bash
git add cococat/routes/skills.py
git commit -m "feat: update skills API routes for unified skills/ directory"
```

---

### Task 9: Cleanup old files and directories

**Files:**
- Delete: `skills/registry.json`
- Delete: `skills/public/list_me.md`
- Delete: `skills/public/knowledge-ingestion.md`
- Delete: `skills/public/` (directory)
- Delete: `skills/private/strategy.md`
- Delete: `skills/private/` (directory)
- Delete: `scenes/development/skills/code_review.md`
- Delete: `scenes/development/skills/prd_writing.md`
- Delete: `scenes/development/skills/manifest.json`
- Delete: `scenes/development/skills/` (directory)
- Delete: `scenes/development/CONTEXT.md`
- Delete: `scenes/development/mounted_kbs.json`
- Delete: `scenes/development/roster.json`
- Delete: `scenes/customer-service/skills/manifest.json`
- Delete: `scenes/customer-service/skills/` (directory)
- Delete: `scenes/customer-service/CONTEXT.md`
- Delete: `scenes/customer-service/scene.json`
- Delete: `scenes/customer-service/config.json`
- Delete: `scenes/default/skills/manifest.json`
- Delete: `scenes/default/skills/` (directory)
- Delete: `scenes/default/CONTEXT.md`
- Delete: `agents/leader/skills/manifest.json`
- Delete: `agents/leader/skills/` (directory)
- Delete: `agents/employee_a/skills/manifest.json`
- Delete: `agents/employee_a/skills/` (directory)
- Delete: `agents/employee_b/skills/manifest.json`
- Delete: `agents/employee_b/skills/` (directory)

- [ ] **Step 1: Remove all old files**

```bash
rm -f skills/registry.json
rm -f skills/public/list_me.md
rm -f skills/public/knowledge-ingestion.md
rmdir skills/public 2>/dev/null || true
rm -f skills/private/strategy.md
rmdir skills/private 2>/dev/null || true
rm -rf scenes/development/skills
rm -f scenes/development/CONTEXT.md
rm -f scenes/development/mounted_kbs.json
rm -f scenes/development/roster.json
rm -rf scenes/customer-service/skills
rm -f scenes/customer-service/CONTEXT.md
rm -f scenes/customer-service/scene.json
rm -f scenes/customer-service/config.json
rm -rf scenes/default/skills
rm -f scenes/default/CONTEXT.md
rm -rf agents/leader/skills
rm -rf agents/employee_a/skills
rm -rf agents/employee_b/skills
```

- [ ] **Step 2: Verify scenes still load correctly**

Run:
```bash
python -c "
from cococat.scene.config import load_scene_config, list_scenes
scenes = list_scenes()
for s in scenes:
    print(f'{s.id}: kbs={s.kbs}, skills={s.skills}')
"
```
Expected: all three scenes print with correct kbs and skills.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove old skill files, manifests, and legacy configs"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/cococat/ -v`
Expected: all tests pass.

- [ ] **Step 2: Start app and hit skills API**

Run:
```bash
python -m uvicorn cococat.app:app --port 8000 --reload &
sleep 2
curl -s http://localhost:8000/api/skills | python -m json.tool
curl -s http://localhost:8000/api/skills/code_review | python -m json.tool
curl -s "http://localhost:8000/api/skills?tag=development" | python -m json.tool
kill %1 2>/dev/null
```
Expected: API returns correct skill lists, filtered by tag.

- [ ] **Step 3: Verify Docker build if applicable**

Run: `docker compose build 2>/dev/null || echo "no docker compose"`
