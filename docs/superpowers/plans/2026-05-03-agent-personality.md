# Agent Personality System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add immutable personality profiles (profile.json) to agents, with a two-phase hire flow (Leader creates pending request → human confirms via terminal or Web → hire executes).

**Architecture:** Hybrid structured+freeform profile schema. Existing hire flow split into `pending/` and `approved/` subdirectories. Personality injected into agent system prompt at runtime.

**Tech Stack:** Rust (core engine), Python (agent runtime), FastAPI (web panel)

---

### Task 1: Add profile loading to context.py

**Files:**
- Modify: `py-agent/context.py`
- Create: `tests/test_context.py` (modify existing)

- [ ] **Step 1: Write failing test for profile loading**

Add to `tests/test_context.py`:

```python
import json, os, tempfile

def test_load_agent_profile():
    from context import load_agent_profile
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "agents", "test_a", "memory"))
        profile = {"role": "工程师", "objective": "写代码", "traits": ["细心"], "background": "", "rules": []}
        profile_path = os.path.join(tmp, "agents", "test_a", "profile.json")
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f)
        result = load_agent_profile("test_a", base_dir=tmp)
        assert result == profile

def test_load_agent_profile_missing():
    from context import load_agent_profile
    result = load_agent_profile("nonexistent")
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_context.py::test_load_agent_profile tests/test_context.py::test_load_agent_profile_missing -v`
Expected: FAIL with "cannot import name 'load_agent_profile'"

- [ ] **Step 3: Add load_agent_profile() to context.py**

Add before `build_system_prompt`:

```python
def load_agent_profile(agent_id: str, base_dir: str = "") -> dict | None:
    """Load agent's profile.json. Returns None if not found."""
    import os as _os
    base = base_dir or _os.path.dirname(_os.path.abspath(__file__))
    profile_path = _os.path.join(base, "..", "agents", agent_id, "profile.json")
    if not _os.path.exists(profile_path):
        return None
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
```

- [ ] **Step 4: Write failing test for profile in system prompt**

```python
def test_build_system_prompt_with_profile():
    from context import build_system_prompt
    profile = {
        "role": "资深工程师",
        "objective": "代码审查",
        "traits": ["细心", "语气:专业"],
        "background": "有10年经验",
        "rules": ["先测试再合并"],
    }
    prompt = build_system_prompt(agent_name="测试员", agent_id="tester", profile=profile)
    assert "资深工程师" in prompt
    assert "代码审查" in prompt
    assert "语气:专业" in prompt
    assert "有10年经验" in prompt
    assert "先测试再合并" in prompt
```

- [ ] **Step 5: Update build_system_prompt() in context.py**

Modify `build_system_prompt()` signature to accept `profile` parameter and template:

```python
SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, a capable AI agent in the CocoCat multi-agent team.

## Identity
- Name: {agent_name}
- ID: {agent_id}
- Current Scene: {scene_name}
{profile_section}
## Scene Context
{scene_context}

## Active Skills
{agent_skills}

## Scene Skills
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

def _build_profile_section(profile: dict | None) -> str:
    if not profile:
        return ""
    lines = []
    lines.append(f"\n## Your Profile")
    lines.append(f"角色: {profile.get('role', '')}")
    lines.append(f"目标: {profile.get('objective', '')}")
    traits = profile.get("traits", [])
    if traits:
        lines.append(f"特质: {', '.join(traits)}")
    rules = profile.get("rules", [])
    if rules:
        lines.append("行为准则:")
        for r in rules:
            lines.append(f"- {r}")
    bg = profile.get("background", "")
    if bg:
        lines.append(f"\n背景故事:\n{bg}")
    return "\n".join(lines)


def build_system_prompt(
    agent_id: str = "unknown",
    agent_name: str = "Agent",
    tool_descriptions: str = "",
    workspace: str = "",
    scene_name: str = "default",
    scene_context: str = "General-purpose work environment.",
    agent_memory: str = "",
    agent_skills: str = "",
    env_skills: str = "",
    profile: dict | None = None,
) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_id=agent_id,
        agent_name=agent_name,
        tool_descriptions=tool_descriptions,
        workspace=workspace or os.getcwd(),
        scene_name=scene_name,
        scene_context=scene_context,
        agent_memory=agent_memory or "(No long-term memories yet)",
        agent_skills=agent_skills or "(No specific skills assigned)",
        env_skills=env_skills or "(No special skills for this scene)",
        profile_section=_build_profile_section(profile),
    )
```

- [ ] **Step 6: Run tests to verify pass**

Run: `python -m pytest tests/test_context.py -v`
Expected: all tests PASS

- [ ] **Step 7: Commit**

Run:
```bash
git add py-agent/context.py tests/test_context.py
git commit -m "feat: add profile loading and system prompt injection for agent personality"
```

---

### Task 2: Wire profile into AgentLoop

**Files:**
- Modify: `py-agent/agent_loop.py`

- [ ] **Step 1: Update AgentLoop.__init__ and _build_system_prompt to pass profile**

In `agent_loop.py`, add import and profile loading:

```python
from context import build_system_prompt, build_tool_descriptions, load_agent_memory, load_agent_skills, load_agent_profile
```

In `_build_system_prompt`:

```python
def _build_system_prompt(self):
    tool_defs = self.tools.get_definitions()
    tool_desc = build_tool_descriptions(tool_defs)
    agent_memory = load_agent_memory(self.agent_id)
    agent_profile = load_agent_profile(self.agent_id)
    return build_system_prompt(
        agent_id=self.agent_id, agent_name=self.agent_name,
        tool_descriptions=tool_desc, workspace=self.workspace,
        scene_name=self.scene_name, scene_context=self.scene_context,
        agent_memory=agent_memory, agent_skills="", env_skills=self.scene_skills,
        profile=agent_profile,
    )
```

In `run()` method, same change for the `build_system_prompt` call (around line 238):

```python
agent_profile = load_agent_profile(self.agent_id)
system_prompt = build_system_prompt(
    agent_id=self.agent_id,
    agent_name=self.agent_name,
    tool_descriptions=tool_desc,
    workspace=self.workspace,
    scene_name=self.scene_name,
    scene_context=self.scene_context,
    agent_memory=agent_memory,
    agent_skills=agent_skills,
    env_skills=self.scene_skills,
    profile=agent_profile,
)
```

- [ ] **Step 2: Run existing tests to verify nothing broken**

Run: `python -m pytest tests/ -v`
Expected: existing tests PASS

- [ ] **Step 3: Commit**

Run:
```bash
git add py-agent/agent_loop.py
git commit -m "feat: wire agent profile into AgentLoop system prompt"
```

---

### Task 3: Extend HireAgentTool with profile parameter + pending directory

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Update HireAgentTool.parameters and execute**

Change `HireAgentTool` to write to `pending/` subdirectory with profile:

```python
class HireAgentTool(Tool):
    """Request hiring a new agent. Creates a pending hire request for admin confirmation."""
    name = "hire_agent"
    required_permission = PermissionMode.FULL_ACCESS
    description = "Request hiring a new team member. Specify id, name, scene, and personality profile."
    parameters = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Unique ID for the new agent (e.g. employee_d)"},
            "name": {"type": "string", "description": "Display name for the new agent (e.g. 员工D)"},
            "scene": {"type": "string", "description": "Scene to assign the agent to (e.g. default)"},
            "role": {"type": "string", "description": "Role title (e.g. 资深工程师)"},
            "objective": {"type": "string", "description": "Core mission/objective"},
            "traits": {
                "type": "array", "items": {"type": "string"},
                "description": "Personality traits, supports key:value format (e.g. 语气:专业)",
            },
            "background": {"type": "string", "description": "Optional backstory (free text)"},
            "rules": {
                "type": "array", "items": {"type": "string"},
                "description": "Behavior rules",
            },
        },
        "required": ["id", "name", "role"],
    }

    def execute(self, id="", name="", scene="default", role="", objective="", traits=None, background="", rules=None, **kwargs) -> str:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        pending_dir = os.path.join(script_dir, "..", "agents", "hire_requests", "pending")
        os.makedirs(pending_dir, exist_ok=True)
        profile = {
            "role": role,
            "objective": objective,
            "traits": traits or [],
            "background": background,
            "rules": rules or [],
        }
        request = {
            "id": id,
            "name": name,
            "scene": scene,
            "profile": profile,
            "status": "pending",
        }
        filepath = os.path.join(pending_dir, f"{id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(request, f, ensure_ascii=False, indent=2)
        return f"Hire request created for '{name}' ({id}) with role '{role}'. Waiting for admin confirmation."
```

- [ ] **Step 2: Write test for HireAgentTool**

```python
def test_hire_agent_tool_pending():
    from tools import HireAgentTool
    import tempfile, os, json
    with tempfile.TemporaryDirectory() as tmp:
        # Create agents/hire_requests/pending/
        os.makedirs(os.path.join(tmp, "agents", "hire_requests", "pending"))
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            tool = HireAgentTool()
            result = tool.execute(
                id="test_d", name="测试D", scene="default",
                role="测试工程师", objective="运行测试",
                traits=["细心", "语气:专业"],
            )
            assert "pending" in result
            pending_file = os.path.join(tmp, "agents", "hire_requests", "pending", "test_d.json")
            assert os.path.exists(pending_file)
            with open(pending_file) as f:
                data = json.load(f)
            assert data["id"] == "test_d"
            assert data["profile"]["role"] == "测试工程师"
            assert data["status"] == "pending"
        finally:
            os.chdir(old_cwd)
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/test_tools.py::test_hire_agent_tool_pending -v`
Expected: PASS

- [ ] **Step 4: Commit**

Run:
```bash
git add py-agent/tools.py tests/test_tools.py
git commit -m "feat: extend HireAgentTool with profile field and pending directory"
```

---

### Task 4: Rust two-phase hire flow

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Write failing Rust test for pending directory scanning**

Add to `tests/` or modify existing test. Create `tests/hire_test.rs`:

```rust
#[test]
fn test_pending_hire_dir_created() {
    use std::fs;
    let pending = "agents/hire_requests/pending";
    let _ = fs::remove_dir_all("agents/hire_requests");
    let _ = fs::create_dir_all(pending);
    assert!(fs::metadata(pending).is_ok());
    let _ = fs::remove_dir_all("agents/hire_requests");
}
```

- [ ] **Step 2: Run Rust test**

Run: `cargo test --test hire_test`
Expected: FAIL (if test file doesn't exist yet) or PASS

- [ ] **Step 3: Refactor process_hire_requests in main.rs into two-phase**

Add after the existing `check_user_questions()` function (or modify `process_hire_requests`):

```rust
fn process_pending_hires() {
    let pending_dir = std::path::Path::new("agents/hire_requests/pending");
    if !pending_dir.exists() {
        return;
    }
    let entries = match std::fs::read_dir(pending_dir) {
        Ok(e) => e,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        if path.file_name().and_then(|n| n.to_str()).map_or(false, |n| n.contains(".processed")) {
            continue;
        }
        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let req: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };
        let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("?");
        let role = req.get("profile").and_then(|p| p.get("role")).and_then(|v| v.as_str()).unwrap_or("?");
        println!("\n===== Pending Hire Request =====");
        println!("  Name: {} ({})", name, req.get("id").and_then(|v| v.as_str()).unwrap_or("?"));
        println!("  Role: {}", role);
        println!("  Scene: {}", req.get("scene").and_then(|v| v.as_str()).unwrap_or("default"));
        if let Some(profile) = req.get("profile") {
            if let Some(objective) = profile.get("objective").and_then(|v| v.as_str()) {
                if !objective.is_empty() {
                    println!("  Objective: {}", objective);
                }
            }
            if let Some(traits) = profile.get("traits").and_then(|v| v.as_array()) {
                let t: Vec<&str> = traits.iter().filter_map(|v| v.as_str()).collect();
                if !t.is_empty() {
                    println!("  Traits: {}", t.join(", "));
                }
            }
        }
        println!("================================");

        let question = serde_json::json!({
            "question": format!("Approve hire '{}' ({})? You can modify the profile above.", name, req.get("id").and_then(|v| v.as_str()).unwrap_or("")),
            "options": ["Approve", "Modify and Approve", "Reject"],
        });
        let question_path = std::path::Path::new("agents/_ask_user.json");
        let _ = std::fs::write(question_path, serde_json::to_string_pretty(&question).unwrap());

        println!("  Waiting for admin response...");
        loop {
            std::thread::sleep(std::time::Duration::from_millis(500));
            let resp_content = match std::fs::read_to_string(question_path) {
                Ok(c) => c,
                Err(_) => continue,
            };
            let resp: serde_json::Value = match serde_json::from_str(&resp_content) {
                Ok(v) => v,
                Err(_) => continue,
            };
            if resp.get("status").and_then(|v| v.as_str()) == Some("answered") {
                let answer = resp.get("answer").and_then(|v| v.as_str()).unwrap_or("").to_string();
                if answer == "Approve" || answer == "Modify and Approve" {
                    // Move to approved directory
                    let approved_dir = std::path::Path::new("agents/hire_requests/approved");
                    let _ = std::fs::create_dir_all(approved_dir);
                    let dest = approved_dir.join(path.file_name().unwrap());
                    let _ = std::fs::rename(&path, &dest);
                    println!("  Hire request moved to approved.\n");
                } else {
                    let rejected_dir = std::path::Path::new("agents/hire_requests/rejected");
                    let _ = std::fs::create_dir_all(rejected_dir);
                    let dest = rejected_dir.join(path.file_name().unwrap());
                    let _ = std::fs::rename(&path, &dest);
                    println!("  Hire request rejected.\n");
                }
                // Mark as processed to avoid re-prompting
                let processed_path = path.with_extension("json.processed");
                let _ = std::fs::write(&processed_path, "");
                break;
            }
        }
    }
}
```

Update `process_hire_requests` to scan `approved/` instead of top-level `hire_requests/`:

```rust
fn process_hire_requests(registry: &mut AgentRegistry) {
    let hire_dir = std::path::Path::new("agents/hire_requests/approved");
    if !hire_dir.exists() {
        return;
    }
    // ... rest stays the same but reads from approved/
    let entries = match fs::read_dir(hire_dir) {
        Ok(e) => e,
        Err(_) => return,
    };
    // ... same loop, but add profile.json writing after spawning
    for entry in entries.flatten() {
        // ... existing logic ...
        // After spawning, also write profile.json if present
        let profile = hire.get("profile");
        if let Some(p) = profile {
            let profile_path = format!("agents/{}/profile.json", new_id);
            let _ = fs::write(&profile_path, serde_json::to_string_pretty(p).unwrap());
        }
        // ... rest ...
    }
}
```

Also add call to `process_pending_hires()` in main loop, before `process_hire_requests`:

```rust
// In main(), after spawning agents:
process_pending_hires();
// Then:
process_hire_requests(&mut registry);
```

- [ ] **Step 4: Run cargo build to verify compilation**

Run: `cargo build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

Run:
```bash
git add src/main.rs
git commit -m "feat: two-phase hire flow - pending confirmation then approved execution"
```

---

### Task 5: Web panel hiring endpoints

**Files:**
- Modify: `web/main.py`
- Modify: `web/routes/agents.py`

- [ ] **Step 1: Add hiring API endpoints to web/main.py**

Add before `@app.get("/", response_class=HTMLResponse)`:

```python
@app.get("/api/hiring/pending")
def list_pending_hires():
    pending_dir = BASE_DIR / "agents" / "hire_requests" / "pending"
    if not pending_dir.exists():
        return {"pending": []}
    hires = []
    for f in sorted(pending_dir.iterdir()):
        if f.suffix == ".json" and ".processed" not in f.name:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                hires.append(data)
            except Exception:
                pass
    return {"pending": hires}


@app.post("/api/hiring/pending/{hire_id}/approve")
async def approve_hire(hire_id: str, request: Request):
    pending_dir = BASE_DIR / "agents" / "hire_requests" / "pending"
    approved_dir = BASE_DIR / "agents" / "hire_requests" / "approved"
    file_path = pending_dir / f"{hire_id}.json"
    if not file_path.exists():
        return JSONResponse({"error": "hire request not found"}, status_code=404)
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    if body and "profile" in body:
        # Apply modifications from admin
        data = json.loads(file_path.read_text(encoding="utf-8"))
        data["profile"] = body["profile"]
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.makedirs(str(approved_dir), exist_ok=True)
    dest = approved_dir / f"{hire_id}.json"
    shutil.move(str(file_path), str(dest))
    return {"status": "approved", "hire_id": hire_id}


@app.post("/api/hiring/pending/{hire_id}/reject")
async def reject_hire(hire_id: str):
    pending_dir = BASE_DIR / "agents" / "hire_requests" / "pending"
    rejected_dir = BASE_DIR / "agents" / "hire_requests" / "rejected"
    file_path = pending_dir / f"{hire_id}.json"
    if not file_path.exists():
        return JSONResponse({"error": "hire request not found"}, status_code=404)
    os.makedirs(str(rejected_dir), exist_ok=True)
    dest = rejected_dir / f"{hire_id}.json"
    shutil.move(str(file_path), str(dest))
    return {"status": "rejected", "hire_id": hire_id}
```

Add `import shutil` at the top.

- [ ] **Step 2: Add hiring section to Web dashboard HTML**

In the dashboard HTML (the string returned by `dashboard()`), add after the Skills div:

```html
<div class="bg-white p-4 rounded shadow">
  <h2 class="font-semibold mb-3">Pending Hires</h2>
  <div id="pending-hires" class="text-sm">Loading...</div>
</div>
```

And add JS to load and interact with pending hires. Add in the `<script>` block:

```javascript
async function loadPendingHires() {
  const el = document.getElementById('pending-hires');
  const resp = await fetch('/api/hiring/pending');
  const data = await resp.json();
  if (!data.pending || data.pending.length === 0) {
    el.innerHTML = '<div class="text-gray-400">No pending hires</div>';
    return;
  }
  el.innerHTML = data.pending.map(h => `
    <div class="border-b border-gray-100 py-2">
      <strong>${h.name}</strong> (${h.id})<br>
      <span class="text-gray-500">Role: ${h.profile?.role || '?'}</span><br>
      <span class="text-gray-500">Scene: ${h.scene}</span>
      ${(h.profile?.traits||[]).length ? '<br><span class="text-gray-400">Traits: ' + h.profile.traits.join(', ') + '</span>' : ''}
      <div class="mt-2 flex gap-2">
        <button onclick="approveHire('${h.id}')" class="bg-green-500 text-white px-3 py-1 text-xs rounded">Approve</button>
        <button onclick="rejectHire('${h.id}')" class="bg-red-500 text-white px-3 py-1 text-xs rounded">Reject</button>
      </div>
    </div>
  `).join('');
}
async function approveHire(id) {
  await fetch('/api/hiring/pending/' + id + '/approve', {method: 'POST'});
  loadPendingHires();
}
async function rejectHire(id) {
  await fetch('/api/hiring/pending/' + id + '/reject', {method: 'POST'});
  loadPendingHires();
}
```

And call `loadPendingHires()` in the existing `load()` function.

- [ ] **Step 3: Basic test (start server and check endpoint)**

Run: `python -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 4: Commit**

Run:
```bash
git add web/main.py web/routes/agents.py
git commit -m "feat: add hiring pending/approve/reject endpoints and dashboard UI"
```

---

### Task 6: Immutability enforcement

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Add profile.json existence check in main.rs hire flow**

In the `process_hire_requests` function, add check before writing profile.json:

```rust
// In process_hire_requests, when writing profile.json:
let profile_path = format!("agents/{}/profile.json", new_id);
if !std::path::Path::new(&profile_path).exists() {
    if let Some(p) = hire.get("profile") {
        let _ = fs::write(&profile_path, serde_json::to_string_pretty(p).unwrap());
    }
} else {
    println!("  Profile already exists for '{}', skipping (immutable).", new_id);
}
```

This guarantees the profile is written exactly once — on the first hire — and never overwritten.

- [ ] **Step 2: Build and verify**

Run: `cargo build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

Run:
```bash
git add src/main.rs
git commit -m "feat: enforce profile immutability - write-once guard in hire flow"
```

---

### Task 7: End-to-end verification

**Files:**
- (no new files)

- [ ] **Step 1: Run all existing tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

Run: `cargo test`
Expected: ALL PASS

- [ ] **Step 2: Manual flow verification**

1. Create a pending hire: create `agents/hire_requests/pending/new_dev.json`:
```json
{"id": "new_dev", "name": "开发者", "scene": "development", "profile": {"role": "全栈工程师", "objective": "开发功能", "traits": ["细心"], "background": "", "rules": []}, "status": "pending"}
```

2. Start CocoCat core and verify it prompts for confirmation

3. Confirm via terminal, or via web panel

4. Verify `agents/new_dev/profile.json` is created

5. Verify `agents/new_dev/profile.json` contents match

6. Start agent runtime and verify profile is in system prompt

- [ ] **Step 3: Final commit**

Run:
```bash
git add -A
git commit -m "feat: complete agent personality system"
```
