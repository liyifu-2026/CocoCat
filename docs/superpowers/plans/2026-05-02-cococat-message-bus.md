# Group Chat Message Bus Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Rust message bus enabling agents to send messages to each other. Messages are logged to a shared chat history file. The `dispatch_task` tool actually works — routes through Rust to target agent.

**Architecture:** A new Rust `message_bus` module maintains a message queue and routes between agents. After each task completes, Rust checks if the result contains a dispatch request. If so, it forwards the message to the target agent and returns the response. All messages are logged to `chat/group.jsonl`.

---

## File Structure

```
Cococlaw/
├── src/
│   ├── main.rs                       # MODIFIED: message routing loop
│   ├── agent_manager.rs              # Unchanged
│   ├── agent_registry.rs             # MODIFIED: + dispatch_message (existing)
│   ├── message_bus.rs                # NEW: message routing + chat log
│   └── transport.rs                  # Unchanged
├── py-agent/
│   ├── tools.py                      # MODIFIED: dispatch_task actually works
│   └── ...                           # Unchanged
└── chat/
    └── group.jsonl                   # NEW: append-only chat log
```

---

### Task 1: Create chat log directory + message_bus.rs

**Files:**
- Create: `chat/group.jsonl`
- Create: `src/message_bus.rs`

- [ ] **Step 1: Create chat directory and empty log**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\chat" | Out-Null
New-Item -ItemType File -Force -Path "C:\Users\12991\Desktop\Cococlaw\chat\group.jsonl" | Out-Null
```

- [ ] **Step 2: Write message_bus.rs**

```rust
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::fs::OpenOptions;
use std::io::Write;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub timestamp: String,
    pub from: String,
    pub to: String,
    pub content: String,
    pub message_type: String, // "task", "reply", "system"
}

/// Log a chat message to group.jsonl
pub fn log_message(msg: &ChatMessage) -> Result<(), String> {
    let line = serde_json::to_string(msg).map_err(|e| format!("serialize error: {}", e))?;
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open("chat/group.jsonl")
        .map_err(|e| format!("failed to open chat log: {}", e))?;
    writeln!(file, "{}", line).map_err(|e| format!("write error: {}", e))?;
    Ok(())
}

/// Read recent chat messages (last N)
pub fn read_recent(n: usize) -> Result<Vec<ChatMessage>, String> {
    let content = std::fs::read_to_string("chat/group.jsonl")
        .map_err(|e| format!("failed to read chat log: {}", e))?;
    let mut messages: Vec<ChatMessage> = content
        .lines()
        .filter_map(|line| serde_json::from_str(line).ok())
        .collect();
    let len = messages.len();
    if len > n {
        messages = messages.split_off(len - n);
    }
    Ok(messages)
}
```

- [ ] **Step 3: Add dependency to Cargo.toml** (chrono for timestamps)

```toml
[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
toml = "0.8"
chrono = "0.4"
```

- [ ] **Step 4: Add mod to main.rs**

```rust
mod message_bus;
```

- [ ] **Step 5: Build**

```bash
cargo build
```

- [ ] **Step 6: Commit**

```bash
git add chat/group.jsonl src/message_bus.rs Cargo.toml src/main.rs
git commit -m "feat: add message bus module and chat log"
```

---

### Task 2: Implement message routing in main.rs

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Update main.rs with message routing

Replace main.rs with a version that has a proper message routing loop:

```rust
mod transport;
mod agent_manager;
mod agent_registry;
mod message_bus;

use agent_registry::AgentRegistry;
use message_bus::ChatMessage;
use serde_json::json;
use std::time::Instant;

fn main() {
    println!("CocoCat Core starting...\n");

    let configs = AgentRegistry::load_config("agents/config.toml")
        .expect("failed to load agent config");
    println!("Loaded {} agent definitions\n", configs.len());

    for cfg in &configs {
        let status = if cfg.enabled { "enabled" } else { "disabled" };
        println!("  [{status}] {} ({})", cfg.name, cfg.id);
    }
    println!();

    let mut registry = AgentRegistry::new(configs);
    match registry.start_all() {
        Ok(()) => {}
        Err(e) => eprintln!("Warning: some agents failed to spawn: {e}"),
    }

    let running = registry.status().iter().filter(|s| s.running).count();
    println!("Spawned {running} agents\n");

    // Ping all
    println!("--- Health Check ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        let ok = agent.call("ping", None, 0)
            .ok()
            .and_then(|r| r.result)
            .map(|r| r.get("pong") == Some(&json!(true)))
            .unwrap_or(false);
        println!("  {} {} ({})", if ok { "✅" else "❌" }, cfg.name, cfg.id);
    }
    println!();

    // Identify all
    println!("--- Team Roster ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        if let Some(data) = agent.call("identify", None, 0).ok().and_then(|r| r.result) {
            let name = data.get("name").and_then(|v| v.as_str()).unwrap_or("?");
            let id = data.get("id").and_then(|v| v.as_str()).unwrap_or("?");
            println!("  {}: id={id}, name={name}", cfg.id, name);
        }
    }
    println!();

    // === Message Bus Demo ===
    println!("--- Message Bus Demo ---");

    // System: leader enters chat
    message_bus::log_message(&ChatMessage {
        timestamp: chrono::Utc::now().to_rfc3339(),
        from: "system".to_string(),
        to: "*".to_string(),
        content: "Team online. Leader ready.".to_string(),
        message_type: "system".to_string(),
    }).ok();

    // Send task to leader: dispatch work to employee_a
    if let Some(agent) = registry.get("leader") {
        let prompt = concat!(
            "You are the team leader. Your team: employee_a (员工A) and employee_b (员工B).\n\n",
            "Use your dispatch_task tool to send this message to employee_a:\n",
            "\"Hello 员工A, please review the schedule file at agents/schedule.json and report what tasks are assigned to you.\"\n\n",
            "After dispatching, tell me what happened."
        );
        let params = json!({"prompt": prompt});
        let start = Instant::now();
        match agent.call("task", Some(params), 1) {
            Ok(resp) => {
                let elapsed = start.elapsed();
                if let Some(result) = resp.result {
                    let content = result.get("content").and_then(|c| c.as_str()).unwrap_or("(no content)");
                    let iterations = result.get("iterations").and_then(|i| i.as_u64()).unwrap_or(0);

                    message_bus::log_message(&ChatMessage {
                        timestamp: chrono::Utc::now().to_rfc3339(),
                        from: "leader".to_string(),
                        to: "*".to_string(),
                        content: format!("Task completed in {} iterations ({:.1}s)", iterations, elapsed.as_secs_f64()),
                        message_type: "system".to_string(),
                    }).ok();

                    println!("\n  Leader completed in {iterations} iterations ({:.1}s):\n", elapsed.as_secs_f64());
                    for line in content.lines() {
                        println!("    {line}");
                    }

                    // Check if leader created a dispatch file
                    check_and_process_dispatches(&mut registry);
                } else if let Some(err) = resp.error {
                    println!("  Leader error [{}]: {}", err.code, err.message);
                }
            }
            Err(e) => {
                println!("  Leader task failed: {e}");
            }
        }
    }
    println!();

    // Show recent chat log
    println!("--- Recent Chat Log ---");
    match message_bus::read_recent(10) {
        Ok(messages) => {
            for msg in messages {
                let from = if msg.from == "system" { "●" } else { &msg.from };
                let to = if msg.to == "*" { "all" } else { &msg.to };
                println!("  [{from} → {to}] {}", msg.content);
            }
        }
        Err(e) => println!("  Failed to read chat log: {e}"),
    }
    println!();

    println!("CocoCat Core exiting.");
}

/// Check for any dispatch requests created by agents and forward them
fn check_and_process_dispatches(registry: &mut AgentRegistry) {
    // Read the dispatch queue (a directory of JSON request files)
    let dispatch_dir = std::path::Path::new("agents/dispatch_queue");
    if !dispatch_dir.exists() {
        return;
    }

    let entries = match std::fs::read_dir(dispatch_dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }

        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let dispatch: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let target_id = dispatch.get("target_id").and_then(|v| v.as_str()).unwrap_or("");
        let method = dispatch.get("method").and_then(|v| v.as_str()).unwrap_or("task");
        let params = dispatch.get("params");

        if !target_id.is_empty() {
            println!("  Routing dispatch to '{}'...", target_id);
            match registry.dispatch_message(target_id, method, params.cloned()) {
                Ok(response) => {
                    println!("  ✅ Dispatch to '{}' succeeded", target_id);
                    if let Some(result) = response.result {
                        if let Some(content) = result.get("content").and_then(|c| c.as_str()) {
                            println!("  Response: {:.100}", content);
                        }
                    }
                }
                Err(e) => {
                    println!("  ❌ Dispatch to '{}' failed: {}", target_id, e);
                }
            }
        }

        // Remove processed dispatch
        let _ = std::fs::remove_file(&path);
    }
}
```

- [ ] **Step 2: Build**

```bash
cargo build
```

- [ ] **Step 3: Commit**

```bash
git add src/message_bus.rs src/main.rs Cargo.toml
git commit -m "feat: message bus with dispatch routing and chat log"
chore: add chrono dependency"
```

---

### Task 3: Update Python dispatch_task to write dispatch files

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Update DispatchTaskTool.execute() to write a dispatch file**

Replace the execute method:

```python
    def execute(self, target_id="", prompt="", **kwargs) -> str:
        """Write a dispatch request file that Rust will read and forward."""
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        queue_dir = os.path.join(script_dir, "..", "agents", "dispatch_queue")
        os.makedirs(queue_dir, exist_ok=True)

        dispatch = {
            "__dispatch__": True,
            "target_id": target_id,
            "method": "task",
            "params": {"prompt": prompt},
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

        # Use a unique filename to avoid conflicts
        filename = f"dispatch_{target_id}_{__import__('time').time_ns()}.json"
        filepath = os.path.join(queue_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dispatch, f, ensure_ascii=False)

        return f"Dispatch request queued for '{target_id}'. The message will be forwarded after your task completes. Message: '{prompt[:80]}...'"
```

- [ ] **Step 2: Test**

```powershell
python -c "from tools import DispatchTaskTool; print('import ok')"
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: dispatch_task writes dispatch files for Rust routing"
```

---

### Task 4: Full integration test

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

Expected:
- 3 agents spawn, ping OK
- Leader uses dispatch_task to send message to employee_a
- Rust routes the dispatch
- Chat log shows the interaction

- [ ] **Step 2: Commit any final fixes**

```bash
git add -A
git commit -m "feat: working message bus with agent dispatch"
```

---

## Summary

After this phase:
- ✅ `message_bus.rs` — message routing + chat logging
- ✅ Dispatch queue — agents write dispatch files, Rust routes them
- ✅ Chat log (`chat/group.jsonl`) — append-only message history
- ✅ Leader can dispatch tasks to other agents via `dispatch_task`
- ✅ Messages are routed through Rust core

**Next phases:**
- Real-time message bus (async, no polling)
- Group chat display in web panel
- Scene management
