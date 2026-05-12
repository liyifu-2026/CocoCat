# Skill Learning/Forgetting Plan

**Goal:** Agents can learn new skills and forget old ones using tools. Skills are persisted in their manifest.

---

### Task 1: Add learn_skill, forget_skill, list_skills tools

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Add three new tools after SendMessageTool**

`LearnSkillTool`:
```python
class LearnSkillTool(Tool):
    """Learn a new skill. The skill .md file must exist in skills/private/ or skills/public/."""
    name = "learn_skill"
    description = "Learn a new skill and add it to your permanent skill set."
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Name of the skill to learn (e.g. code_review)"},
        },
        "required": ["skill_name"],
    }

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, skill_name="", **kwargs) -> str:
        import os, json
        base = os.path.dirname(os.path.abspath(__file__))
        manifest_path = os.path.join(base, "..", "agents", self.agent_id, "skills", "manifest.json")
        if not os.path.exists(manifest_path):
            return f"No manifest found for agent '{self.agent_id}'"
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        if skill_name in manifest.get("private", []):
            return f"Already knows '{skill_name}'"
        manifest.setdefault("private", []).append(skill_name)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        return f"Learned skill '{skill_name}'"
```

`ForgetSkillTool`:
```python
class ForgetSkillTool(Tool):
    """Forget a skill and remove it from your permanent skill set."""
    name = "forget_skill"
    description = "Forget a skill you no longer need."
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "Name of the skill to forget"},
        },
        "required": ["skill_name"],
    }

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, skill_name="", **kwargs) -> str:
        import os, json
        manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", self.agent_id, "skills", "manifest.json")
        if not os.path.exists(manifest_path):
            return "No manifest found"
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        if skill_name not in manifest.get("private", []):
            return f"Does not know '{skill_name}'"
        manifest["private"] = [s for s in manifest["private"] if s != skill_name]
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        return f"Forgot skill '{skill_name}'"
```

`ListSkillsTool`:
```python
class ListSkillsTool(Tool):
    """List all skills you currently have (public + private)."""
    name = "list_skills"
    description = "List all skills you currently have."
    parameters = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, agent_id: str = ""):
        super().__init__()
        self.agent_id = agent_id

    def execute(self, **kwargs) -> str:
        import os, json
        manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", self.agent_id, "skills", "manifest.json")
        if not os.path.exists(manifest_path):
            return "No manifest found"
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        public = manifest.get("public", [])
        private = manifest.get("private", [])
        lines = ["## Public Skills"]
        lines.extend(f"- {s}" for s in public)
        lines.append("\n## Private Skills")
        lines.extend(f"- {s}" for s in private) if private else lines.append("(none)")
        return "\n".join(lines)
```

- [ ] **Step 2: Register in create_default_registry**

```python
    registry.register(LearnSkillTool(agent_id=agent_id))
    registry.register(ForgetSkillTool(agent_id=agent_id))
    registry.register(ListSkillsTool(agent_id=agent_id))
```

- [ ] **Step 3: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from tools import LearnSkillTool, ForgetSkillTool, ListSkillsTool; print('skill tools ok')"
```

```bash
cargo build
python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: add learn_skill, forget_skill, list_skills tools"
```
