# Scene Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Agents work in "scenes" — work contexts that provide scene-specific context, mounted knowledge bases, and env-tagged skills. When an agent enters a scene, it gets the scene's CONTEXT.md injected into its system prompt, and env-tagged skills become available.

**Architecture:** Scene configs live in `scenes/{scene_id}/` with CONTEXT.md, roster, mounted KBs, and env skills. The agent's system prompt is augmented with scene context on each task. Scene assignment is configured per-agent or per-task.

---

## File Structure

```
Cococlaw/
├── scenes/
│   ├── default/
│   │   ├── CONTEXT.md          # Scene description and guidelines
│   │   ├── mounted_kbs.json    # Knowledge bases available in this scene
│   │   ├── skills/manifest.json # env-tagged skills
│   │   └── roster.json         # Agents assigned to this scene
│   └── development/            # Another scene example
│       ├── CONTEXT.md
│       ├── mounted_kbs.json
│       ├── skills/manifest.json
│       └── roster.json
├── agents/
│   └── config.toml             # + scene field per agent
├── src/
│   ├── main.rs                 # Pass scene config to agents
│   └── agent_registry.rs       # Load scene info for each agent
├── py-agent/
│   ├── context.py              # + scene context injection
│   └── tools.py                # + scene-aware skills
```

---

### Task 1: Create scene directory structure

**Files:**
- Create: `scenes/default/CONTEXT.md`
- Create: `scenes/default/mounted_kbs.json`
- Create: `scenes/default/skills/manifest.json`
- Create: `scenes/default/roster.json`
- Create: `scenes/development/CONTEXT.md`
- Create: `scenes/development/mounted_kbs.json`
- Create: `scenes/development/skills/manifest.json`
- Create: `scenes/development/roster.json`

- [ ] **Step 1: Create default scene**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\scenes\default\skills" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\scenes\development\skills" | Out-Null
```

`scenes/default/CONTEXT.md`:
```markdown
# Default Scene

General-purpose work environment for the CocoCat team.

## Guidelines
- All team members are available for general tasks
- Default tools are available to all agents
- No special knowledge bases mounted
```

`scenes/default/mounted_kbs.json`:
```json
{
  "mounted": [],
  "search_mode": "token"
}
```

`scenes/default/skills/manifest.json`:
```json
{
  "env_skills": []
}
```

`scenes/default/roster.json`:
```json
{
  "agents": ["leader", "employee_a", "employee_b"]
}
```

- [ ] **Step 2: Create development scene**

`scenes/development/CONTEXT.md`:
```markdown
# Development Scene

Software development work environment.

## Guidelines
- Focus on code quality, testing, and documentation
- Follow the team's coding standards
- All code changes should be reviewed
- Use sub_agent for complex multi-file changes

## Active Projects
- CocoCat MVP: core agent system
- Message bus integration
```

`scenes/development/mounted_kbs.json`:
```json
{
  "mounted": [],
  "search_mode": "token"
}
```

`scenes/development/skills/manifest.json`:
```json
{
  "env_skills": [
    "code_review",
    "prd_writing"
  ]
}
```

`scenes/development/roster.json`:
```json
{
  "agents": ["leader", "employee_a"]
}
```

- [ ] **Step 3: Commit**

```bash
git add scenes/
git commit -m "feat: add scene directory structure with default and development scenes"
```

---

### Task 2: Add scene field to agent config

**Files:**
- Modify: `agents/config.toml`

- [ ] **Step 1: Update config.toml with scene field**

```toml
[[agents]]
id = "leader"
name = "组长"
interpreter = "python"
script = "py-agent/agent_runtime.py"
enabled = true
scene = "development"

[[agents]]
id = "employee_a"
name = "员工A"
interpreter = "python"
script = "py-agent/agent_runtime.py"
enabled = true
scene = "development"

[[agents]]
id = "employee_b"
name = "员工B"
interpreter = "python"
script = "py-agent/agent_runtime.py"
enabled = true
scene = "default"
```

- [ ] **Step 2: Update AgentConfig struct in agent_registry.rs

Add `scene` field:

```rust
#[derive(Debug, Deserialize, Clone)]
pub struct AgentConfig {
    pub id: String,
    pub name: String,
    pub interpreter: String,
    pub script: String,
    pub enabled: bool,
    pub scene: Option<String>,
}
```

- [ ] **Step 3: Build**

```bash
cargo build
```

- [ ] **Step 4: Commit**

```bash
git add agents/config.toml src/agent_registry.rs
git commit -m "feat: add scene field to agent config"
```

---

### Task 3: Scene context injection into agent system prompt

**Files:**
- Modify: `py-agent/context.py`

- [ ] **Step 1: Update context.py with scene context support**

Add scene context to the system prompt builder:

```python
"""System prompt builder (nanobot ContextBuilder pattern)."""
import os
import json


SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, a capable AI agent in the CocoCat multi-agent team.

## Identity
- Name: {agent_name}
- ID: {agent_id}
- Current Scene: {scene_name}

## Scene Context
{scene_context}

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


def build_system_prompt(
    agent_id: str = "unknown",
    agent_name: str = "Agent",
    tool_descriptions: str = "",
    workspace: str = "",
    scene_name: str = "default",
    scene_context: str = "",
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_descriptions=tool_descriptions,
        workspace=workspace or os.getcwd(),
        scene_name=scene_name,
        scene_context=scene_context or "(No special scene context)",
    )


def load_scene_context(scene_id: str) -> tuple[str, str]:
    """Load scene name and CONTEXT.md content from scenes/{scene_id}/."""
    import os as _os
    scene_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "scenes", scene_id)
    name = scene_id
    context = ""
    context_path = _os.path.join(scene_dir, "CONTEXT.md")
    if _os.path.exists(context_path):
        with open(context_path, "r", encoding="utf-8") as f:
            context = f.read()
    return name, context


def build_tool_descriptions(tools: list[dict]) -> str:
    """Build a human-readable tool list from OpenAI-style tool definitions."""
    lines = []
    for t in tools:
        name = t["function"]["name"]
        desc = t["function"]["description"]
        params = t["function"]["parameters"]
        required = params.get("required", [])
        props = params.get("properties", {})
        param_lines = []
        for pname, pinfo in props.items():
            req = "required" if pname in required else "optional"
            param_lines.append(f"    {pname} ({req}): {pinfo.get('description', '')}")
        param_str = "\n" + "\n".join(param_lines) if param_lines else ""
        lines.append(f"- {name}: {desc}{param_str}")
    return "\n".join(lines)
```

- [ ] **Step 2: Test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from context import load_scene_context; n, c = load_scene_context('default'); print('Scene:', n); print('Context:', c[:50])"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/context.py
git commit -m "feat: add scene context injection to system prompt"
```

---

### Task 4: Pass scene identity to agent and load scene context

**Files:**
- Modify: `src/agent_registry.rs` (pass scene arg to agent)
- Modify: `py-agent/agent_runtime.py` (accept scene arg, inject context)
- Modify: `py-agent/agent_loop.py` (pass scene to context builder)

- [ ] **Step 1: Pass scene arg through spawn**

In `agent_registry.rs`, update `start_all()` to pass `--scene` arg:

```rust
    pub fn start_all(&mut self) -> Result<(), String> {
        for config in &self.configs {
            if !config.enabled {
                continue;
            }
            let mut extra_args = vec!["--id", &config.id, "--name", &config.name];
            if let Some(scene) = &config.scene {
                extra_args.push("--scene");
                extra_args.push(scene);
            }
            let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra_args)?;
            self.processes.insert(config.id.clone(), agent);
        }
        Ok(())
    }
```

- [ ] **Step 2: Accept --scene arg in agent_runtime.py**

Update the `IDENTITY` and arg parsing:

```python
IDENTITY = {"id": None, "name": "unknown", "scene": "default"}
```

Update `main()` args:

```python
    parser.add_argument("--scene", default="default")
    if args.id:
        IDENTITY["id"] = args.id
        IDENTITY["name"] = args.name
        IDENTITY["scene"] = args.scene
```

Update lazy AgentLoop init to pass scene:

```python
            if request.get("method") == "task" and agent_loop is None:
                from agent_loop import AgentLoop
                from tools import create_default_registry
                from context import load_scene_context

                script_dir = os.path.dirname(os.path.abspath(__file__))
                agent_runtime_path = os.path.join(script_dir, "agent_runtime.py")

                # Load scene context
                scene_name, scene_context = load_scene_context(IDENTITY.get("scene", "default"))

                tools = create_default_registry(agent_runtime_path=agent_runtime_path)
                agent_loop = AgentLoop(
                    agent_id=IDENTITY["id"] or "unknown",
                    agent_name=IDENTITY["name"] or "Agent",
                    tools=tools,
                    scene_name=scene_name,
                    scene_context=scene_context,
                )
```

- [ ] **Step 3: Update AgentLoop to accept scene context**

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
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.tools = tools or create_default_registry()
        self.llm = llm or LLMClient()
        self.max_iterations = max_iterations
        self.workspace = workspace
        self.scene_name = scene_name
        self.scene_context = scene_context
```

Update `run()` to pass scene to context builder:

```python
        system_prompt = build_system_prompt(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            tool_descriptions=tool_desc,
            workspace=self.workspace,
            scene_name=self.scene_name,
            scene_context=self.scene_context,
        )
```

- [ ] **Step 4: Build and test**

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
cargo build
cargo run
```

Expected: Agents show their scene in system prompt context. Leader (development scene) gets dev context, employee_b (default scene) gets general context.

- [ ] **Step 5: Commit**

```bash
git add src/agent_registry.rs py-agent/agent_runtime.py py-agent/agent_loop.py agents/config.toml
git commit -m "feat: scene-aware agents with context injection"
```

---

### Task 5: Scene display in main.rs

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Update main.rs to show scene info**

In the identify section, also show scene:

```rust
    if let Some(data) = agent.call("identify", None, 0).ok().and_then(|r| r.result) {
        let id = data.get("id").and_then(|v| v.as_str()).unwrap_or("?");
        let name = data.get("name").and_then(|v| v.as_str()).unwrap_or("?");
        let scene = data.get("scene").and_then(|v| v.as_str()).unwrap_or("?");
        println!("  {}: id={id}, name={name}, scene={scene}", cfg.id, name, scene);
    }
```

- [ ] **Step 2: Build and run**

```bash
cargo build
cargo run
```

Expected: Shows scene for each agent.

- [ ] **Step 3: Commit**

```bash
git add src/main.rs
git commit -m "feat: display scene info in agent roster"
```

---

## Summary

After this phase:
- ✅ Scene directory structure (default, development)
- ✅ Scene config files (CONTEXT.md, roster, mounted KBs, env skills)
- ✅ Agents assigned to scenes via config
- ✅ Scene context injected into system prompt
- ✅ Agent identity includes scene info
- ✅ Different agents can work in different scenes
