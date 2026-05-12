# Hire Agent — Full Flow Implementation Plan

**Goal:** When the leader uses `hire_agent` tool, Rust reads the hire request, updates `agents/config.toml`, spawns the new agent, and logs the event.

**Architecture:** After each agent task, Rust checks `agents/hire_requests/` for pending hires. If found, it reads the request, appends a new `[[agents]]` entry to `config.toml`, spawns the new agent, and removes the request file.

---

### Task 1: Add hire_agent processing in main.rs

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Read current main.rs**

- [ ] **Step 2: Add process_hire_requests() function**

After `check_and_process_dispatches`, add:

```rust
use std::fs;

/// Process pending hire requests from agents/hire_requests/
fn process_hire_requests(registry: &mut AgentRegistry) {
    let hire_dir = std::path::Path::new("agents/hire_requests");
    if !hire_dir.exists() {
        return;
    }

    let entries = match fs::read_dir(hire_dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }

        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let hire: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let new_id = hire.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let new_name = hire.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();

        if new_id.is_empty() || new_name.is_empty() {
            continue;
        }

        println!("  Processing hire request: {} ({})", new_name, new_id);

        // 1. Update config.toml
        let config_path = "agents/config.toml";
        let mut config_content = fs::read_to_string(config_path).unwrap_or_default();

        let new_entry = format!(
            "\n[[agents]]\nid = \"{}\"\nname = \"{}\"\ninterpreter = \"python\"\nscript = \"py-agent/agent_runtime.py\"\nenabled = true\nscene = \"development\"\n",
            new_id, new_name
        );
        config_content.push_str(&new_entry);

        if let Err(e) = fs::write(config_path, &config_content) {
            println!("  ❌ Failed to update config: {e}");
            continue;
        }

        // 2. Create memory directory
        let mem_dir = format!("agents/{}/memory", new_id);
        let _ = fs::create_dir_all(&mem_dir);
        let _ = fs::write(
            format!("{}/MEMORY.md", mem_dir),
            format!("# {} Memory\n\nPersonal memories and learnings.\n", new_name),
        );
        let _ = fs::write(format!("{}/history.jsonl", mem_dir), "");
        let _ = fs::write(format!("{}/.dream_cursor", mem_dir), "0");

        // 3. Add to registry and spawn
        let new_config = agent_registry::AgentConfig {
            id: new_id.clone(),
            name: new_name.clone(),
            interpreter: "python".to_string(),
            script: "py-agent/agent_runtime.py".to_string(),
            enabled: true,
            scene: Some("development".to_string()),
        };
        registry.configs.push(new_config.clone());
        match registry.start_one(new_config) {
            Ok(()) => println!("  ✅ {} ({}) hired and spawned", new_name, new_id),
            Err(e) => println!("  ❌ Failed to spawn {}: {}", new_id, e),
        }

        // 4. Log to chat
        let _ = message_bus::log_message(&message_bus::ChatMessage {
            timestamp: chrono::Utc::now().to_rfc3339(),
            from: "system".to_string(),
            to: "*".to_string(),
            content: format!("New team member hired: {} ({})", new_name, new_id),
            message_type: "system".to_string(),
        });

        // 5. Remove hire request
        let _ = fs::remove_file(&path);
    }
}
```

- [ ] **Step 3: Add start_one to AgentRegistry**

In `src/agent_registry.rs`, add:

```rust
    pub fn start_one(&mut self, config: AgentConfig) -> Result<(), String> {
        if !config.enabled {
            return Ok(());
        }
        let extra = [ "--id", &config.id, "--name", &config.name ];
        let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra)?;
        self.processes.insert(config.id.clone(), agent);
        Ok(())
    }
```

- [ ] **Step 4: Call process_hire_requests in main.rs**

After `check_and_process_dispatches(&mut registry);`, add:

```rust
            process_hire_requests(&mut registry);
```

- [ ] **Step 5: Build and run**

```bash
cargo build
```

- [ ] **Step 6: Commit**

```bash
git add src/main.rs src/agent_registry.rs
git commit -m "feat: hire_agent auto-updates config and spawns new agent"
```

---

### Task 2: End-to-end test

- [ ] **Step 1: Run with hire request**

```powershell
$env:OPENAI_API_KEY = "sk-055b943d0a2d4212a7c8bc0064623a45"
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:LLM_MODEL = "deepseek-v4-flash"
cargo build
```

Then manually test: create a hire request and run:
```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents\hire_requests" | Out-Null
@'
{"id": "employee_c", "name": "员工C", "personality": "Documentation specialist", "requested_by": "leader"}
'@ | Out-File -Encoding utf8 "C:\Users\12991\Desktop\Cococlaw\agents\hire_requests\employee_c.json"
cargo run
```

- [ ] **Step 2: Verify**

Check that employee_c was hired:
```powershell
Select-String -Path "C:\Users\12991\Desktop\Cococlaw\agents\config.toml" -Pattern "employee_c"
Get-Content "C:\Users\12991\Desktop\Cococlaw\agents\employee_c\memory\MEMORY.md"
Get-ChildItem "C:\Users\12991\Desktop\Cococlaw\agents\hire_requests" -ErrorAction SilentlyContinue
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: hire flow verified end-to-end"
```
