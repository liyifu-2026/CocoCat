# Multi-Agent System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Rust core can spawn and manage multiple Python agent processes simultaneously, driven by a TOML config file.

**Architecture:** A TOML config defines agents (id, name, interpreter, script). Rust's `AgentRegistry` reads config, spawns each agent into an `AgentProcess`, provides lookup by id, and handles graceful shutdown. Each Python agent returns its identity via an "identify" method.

**Prerequisites:** MVP (Tasks 1-6) is complete — Rust project skeleton, transport, agent_manager, Python runtime, ping/pong verified.

---

## File Structure

```
Cococlaw/
├── Cargo.toml                       # + toml dependency
├── src/
│   ├── main.rs                      # Load config → spawn all → ping each → exit
│   ├── transport.rs                 # Unchanged
│   ├── agent_manager.rs             # Unchanged (AgentProcess)
│   └── agent_registry.rs            # NEW: config loading, multi-agent management
├── py-agent/
│   └── agent_runtime.py             # + "identify" method
└── agents/
    └── config.toml                  # NEW: agent definitions
```

---

### Task 1: Add `toml` dependency and create agent config

**Files:**
- Modify: `Cargo.toml`
- Create: `agents/config.toml`

- [ ] **Step 1: Add toml dependency to Cargo.toml**

```toml
[package]
name = "cococat"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
toml = "0.8"
```

- [ ] **Step 2: Create agents/config.toml**

```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\12991\Desktop\Cococlaw\agents" | Out-Null
```

```toml
[[agents]]
id = "leader"
name = "组长"
interpreter = "python"
script = "py-agent/agent_runtime.py"
enabled = true

[[agents]]
id = "employee_a"
name = "员工A"
interpreter = "python"
script = "py-agent/agent_runtime.py"
enabled = true

[[agents]]
id = "employee_b"
name = "员工B"
interpreter = "python"
script = "py-agent/agent_runtime.py"
enabled = true
```

- [ ] **Step 3: Build to verify toml dependency resolves**

Run: `cargo build`
Expected: compiles with no new errors (dead-code warnings unchanged)

- [ ] **Step 4: Commit**

```bash
git add Cargo.toml agents/config.toml
git commit -m "feat: add toml dependency and multi-agent config"
```

---

### Task 2: Add "identify" method to Python agent

**Files:**
- Modify: `py-agent/agent_runtime.py`

- [ ] **Step 1: Add identify handler**

Add `IDENTITY` constant and `identify` method handler:

```python
import sys
import json

IDENTITY = {
    "id": None,
    "name": "unknown",
}


def handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "ping":
        return {"pong": True, "agent": "cococat-mvp"}
    elif method == "echo":
        return params
    elif method == "identify":
        return dict(IDENTITY)
    else:
        raise ValueError(f"Method not found: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        req_id = None
        try:
            request = json.loads(line)
            req_id = request.get("id")
            result = handle_request(request)
            response = {"jsonrpc": "2.0", "result": result, "id": req_id}
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {e}"},
                "id": None,
            }
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id,
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    # Allow setting identity via CLI args: python agent_runtime.py --id leader --name 组长
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=None)
    parser.add_argument("--name", default="unknown")
    args, _ = parser.parse_known_args()
    if args.id:
        IDENTITY["id"] = args.id
        IDENTITY["name"] = args.name

    main()
```

- [ ] **Step 2: Test identify method**

```powershell
echo '{"jsonrpc":"2.0","method":"identify","params":{},"id":1}' | python -u py-agent/agent_runtime.py --id leader --name 组长
```

Expected:
```
{"jsonrpc": "2.0", "result": {"id": "leader", "name": "组长"}, "id": 1}
```

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_runtime.py
git commit -m "feat: add identify method and CLI args to Python agent"
```

---

### Task 3: Create AgentRegistry — multi-agent management

**Files:**
- Create: `src/agent_registry.rs`

- [ ] **Step 1: Write agent_registry.rs**

```rust
use crate::agent_manager::AgentProcess;
use serde::Deserialize;
use std::collections::HashMap;

#[derive(Debug, Deserialize, Clone)]
pub struct AgentConfig {
    pub id: String,
    pub name: String,
    pub interpreter: String,
    pub script: String,
    pub enabled: bool,
}

#[derive(Debug, Deserialize)]
pub struct AgentsConfig {
    pub agents: Vec<AgentConfig>,
}

pub struct AgentRegistry {
    pub configs: Vec<AgentConfig>,
    processes: HashMap<String, AgentProcess>,
}

impl AgentRegistry {
    /// Load agent configurations from a TOML file
    pub fn load_config(path: &str) -> Result<Vec<AgentConfig>, String> {
        let content =
            std::fs::read_to_string(path).map_err(|e| format!("failed to read config: {}", e))?;
        let config: AgentsConfig =
            toml::from_str(&content).map_err(|e| format!("failed to parse config: {}", e))?;
        Ok(config.agents)
    }

    /// Create a new registry from configs (does not spawn)
    pub fn new(configs: Vec<AgentConfig>) -> Self {
        Self {
            configs,
            processes: HashMap::new(),
        }
    }

    /// Spawn all enabled agents
    pub fn start_all(&mut self) -> Result<(), String> {
        for config in &self.configs {
            if !config.enabled {
                continue;
            }
            let agent = AgentProcess::spawn(&config.interpreter, &config.script)?;
            self.processes.insert(config.id.clone(), agent);
        }
        Ok(())
    }

    /// Get a reference to an agent's process by id
    pub fn get(&mut self, id: &str) -> Option<&mut AgentProcess> {
        self.processes.get_mut(id)
    }

    /// Get status of all agents
    pub fn status(&self) -> Vec<AgentStatus> {
        self.configs
            .iter()
            .map(|c| AgentStatus {
                id: c.id.clone(),
                name: c.name.clone(),
                enabled: c.enabled,
                running: self.processes.contains_key(&c.id),
            })
            .collect()
    }

    /// Stop all agents and clear the registry
    pub fn stop_all(&mut self) {
        // Dropping the HashMap drops all AgentProcess instances,
        // which triggers their Drop impl (kills subprocess)
        self.processes.clear();
    }
}

#[derive(Debug)]
pub struct AgentStatus {
    pub id: String,
    pub name: String,
    pub enabled: bool,
    pub running: bool,
}
```

- [ ] **Step 2: Add module to main.rs**

```rust
mod agent_registry;
```

- [ ] **Step 3: Build**

Run: `cargo build`
Expected: compiles with only existing warnings

- [ ] **Step 4: Commit**

```bash
git add src/agent_registry.rs src/main.rs
git commit -m "feat: add AgentRegistry for multi-agent management"
```

---

### Task 4: Update main.rs to spawn all agents and ping each

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Replace main.rs with multi-agent version**

```rust
mod transport;
mod agent_manager;
mod agent_registry;

use agent_manager::AgentProcess;
use agent_registry::{AgentConfig, AgentRegistry};

fn main() {
    println!("CocoCat Core starting...\n");

    // 1. Load agent configs
    let configs = AgentRegistry::load_config("agents/config.toml")
        .expect("failed to load agent config");
    println!("Loaded {} agent definitions\n", configs.len());

    // 2. Show configured agents
    for cfg in &configs {
        let status = if cfg.enabled { "enabled" } else { "disabled" };
        println!("  [{status}] {} ({})", cfg.name, cfg.id);
    }
    println!();

    // 3. Spawn all enabled agents
    let mut registry = AgentRegistry::new(configs);
    registry.start_all().expect("failed to spawn agents");

    let statuses = registry.status();
    let running_count = statuses.iter().filter(|s| s.running).count();
    println!("Spawned {running_count} agents\n");

    // 4. Ping each agent
    for cfg in registry.configs.clone() {
        if !cfg.enabled {
            continue;
        }
        let agent = registry.get(&cfg.id).expect("agent should be running");
        let response = agent
            .call("ping", None, 1)
            .expect("failed to ping agent");

        let is_ok = response
            .result
            .map(|r| r.get("pong") == Some(&serde_json::json!(true)))
            .unwrap_or(false);

        let mark = if is_ok { "✅" } else { "❌" };
        println!("  {mark} {}: ping {}", cfg.name, cfg.id);
    }

    // 5. Identify each agent
    for cfg in registry.configs.clone() {
        if !cfg.enabled {
            continue;
        }
        let agent = registry.get(&cfg.id).expect("agent should be running");
        let response = agent.call("identify", None, 2).expect("failed to identify agent");

        if let Some(result) = response.result {
            let agent_id = result.get("id").and_then(|v| v.as_str()).unwrap_or("?");
            let agent_name = result.get("name").and_then(|v| v.as_str()).unwrap_or("?");
            println!("  🆔 {}: id={agent_id}, name={agent_name}", cfg.name);
        }
    }

    println!("\nCocoCat Core exiting.");
    // registry.stop_all() called automatically via Drop
}
```

- [ ] **Step 2: Build**

Run: `cargo build`

- [ ] **Step 3: Run and verify**

Run: `cargo run`

Expected output:
```
CocoCat Core starting...

Loaded 3 agent definitions

  [enabled] 组长 (leader)
  [enabled] 员工A (employee_a)
  [enabled] 员工B (employee_b)

Spawned 3 agents

  ✅ 组长: ping leader
  ✅ 员工A: ping employee_a
  ✅ 员工B: ping employee_b
  🆔 组长: id=?, name=?
  🆔 员工A: id=?, name=?
  🆔 员工B: id=?, name=?
```

Note: `identify` returns `id: null` because we haven't passed --id/--name args to the Python script yet. That's expected — Task 5 fixes this.

- [ ] **Step 4: Commit**

```bash
git add src/main.rs
git commit -m "feat: update main to spawn all agents and ping each"
```

---

### Task 5: Pass identity args to Python agents via spawn

**Files:**
- Modify: `src/agent_manager.rs`
- Modify: `src/agent_registry.rs`

- [ ] **Step 1: Update AgentProcess::spawn to accept extra arguments**

Change `src/agent_manager.rs`:

```rust
use crate::transport::{self, JsonRpcRequest, JsonRpcResponse};
use std::io::{BufReader, Write};
use std::process::{Child, Command, Stdio};

pub struct AgentProcess {
    child: Child,
    stdin_writer: Option<std::process::ChildStdin>,
    stdout_reader: BufReader<std::process::ChildStdout>,
    interpreter: String,
}

impl AgentProcess {
    /// Spawn a Python agent subprocess with optional extra args
    pub fn spawn(
        interpreter: &str,
        python_script_path: &str,
        extra_args: &[&str],
    ) -> Result<Self, String> {
        let mut cmd = Command::new(interpreter);
        cmd.arg("-u").arg(python_script_path);
        for arg in extra_args {
            cmd.arg(arg);
        }
        let mut child = cmd
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("failed to spawn agent: {}", e))?;

        let stdin_writer = child.stdin.take().ok_or("failed to open agent stdin")?;
        let stdout_reader = BufReader::new(child.stdout.take().ok_or("failed to open agent stdout")?);

        Ok(Self {
            child,
            stdin_writer: Some(stdin_writer),
            stdout_reader,
            interpreter: interpreter.to_string(),
        })
    }

    pub fn call(&mut self, method: &str, params: Option<serde_json::Value>, id: u64) -> Result<JsonRpcResponse, String> {
        let req = JsonRpcRequest::new(method, params, id);
        transport::send_request(
            self.stdin_writer.as_mut().ok_or("agent already terminated")?,
            &req,
        )?;
        transport::read_response(&mut self.stdout_reader)
    }

    pub fn kill(&mut self) -> Result<(), String> {
        if let Some(ref mut child) = self.child.try_wait().map_err(|e| format!("wait error: {}", e))? {
            return Ok(()); // already exited
        }
        self.child
            .kill()
            .map_err(|e| format!("failed to kill agent: {}", e))
    }

    pub fn wait(&mut self) -> Result<(), String> {
        drop(self.stdin_writer.take());
        self.child
            .wait()
            .map_err(|e| format!("failed to wait for agent: {}", e))?;
        Ok(())
    }
}

impl Drop for AgentProcess {
    fn drop(&mut self) {
        let _ = self.stdin_writer.take();
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
```

Key changes:
1. `spawn()` now accepts `extra_args: &[&str]` — appends them after the script path
2. `stdin_writer` is now `Option<ChildStdin>` instead of `ChildStdin` (so we can take() it in wait() and Drop)
3. Updated all methods to work with `Option<ChildStdin>`

- [ ] **Step 2: Update AgentRegistry to pass identity args**

Update `src/agent_registry.rs` — the `start_all()` method:

```rust
    pub fn start_all(&mut self) -> Result<(), String> {
        for config in &self.configs {
            if !config.enabled {
                continue;
            }
            let extra_args = [
                "--id",
                &config.id,
                "--name",
                &config.name,
            ];
            let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra_args)?;
            self.processes.insert(config.id.clone(), agent);
        }
        Ok(())
    }
```

- [ ] **Step 3: Build**

Run: `cargo build`

- [ ] **Step 4: Run and verify identity works**

Run: `cargo run`

Expected output shows identities:
```
  🆔 组长: id=leader, name=组长
  🆔 员工A: id=employee_a, name=员工A
  🆔 员工B: id=employee_b, name=员工B
```

- [ ] **Step 5: Commit**

```bash
git add src/agent_manager.rs src/agent_registry.rs
git commit -m "feat: pass identity args to Python agents via spawn"
```

---

### Task 6: Add graceful shutdown and error handling

**Files:**
- Modify: `src/main.rs`

- [ ] **Step 1: Update main.rs with error resilience**

Replace main() with version that handles partial failures:

```rust
mod transport;
mod agent_manager;
mod agent_registry;

use agent_registry::AgentRegistry;

fn main() {
    println!("CocoCat Core starting...\n");

    // 1. Load config
    let configs = AgentRegistry::load_config("agents/config.toml")
        .expect("failed to load agent config");
    println!("Loaded {} agent definitions\n", configs.len());

    // 2. Show configured agents
    for cfg in &configs {
        let status = if cfg.enabled { "enabled" } else { "disabled" };
        println!("  [{status}] {} ({})", cfg.name, cfg.id);
    }
    println!();

    // 3. Spawn agents, allowing partial failures
    let mut registry = AgentRegistry::new(configs);
    match registry.start_all() {
        Ok(()) => {}
        Err(e) => eprintln!("Warning: some agents failed to spawn: {e}"),
    }

    let statuses = registry.status();
    let running_count = statuses.iter().filter(|s| s.running).count();
    println!("Spawned {running_count} agents\n");

    // 4. Ping each running agent
    for cfg in registry.configs.clone() {
        if !cfg.enabled {
            continue;
        }
        let Some(agent) = registry.get(&cfg.id) else {
            println!("  ⚠️  {}: not running", cfg.name);
            continue;
        };
        let response = match agent.call("ping", None, 1) {
            Ok(r) => r,
            Err(e) => {
                println!("  ❌ {}: ping failed — {e}", cfg.name);
                continue;
            }
        };
        let is_ok = response
            .result
            .map(|r| r.get("pong") == Some(&serde_json::json!(true)))
            .unwrap_or(false);
        let mark = if is_ok { "✅" } else { "❌" };
        println!("  {mark} {} ({})", cfg.name, cfg.id);
    }

    // 5. Identify each running agent
    for cfg in registry.configs.clone() {
        if !cfg.enabled {
            continue;
        }
        let Some(agent) = registry.get(&cfg.id) else {
            continue;
        };
        let response = match agent.call("identify", None, 2) {
            Ok(r) => r,
            Err(_) => continue,
        };
        if let Some(result) = response.result {
            let agent_id = result.get("id").and_then(|v| v.as_str()).unwrap_or("?");
            let agent_name = result.get("name").and_then(|v| v.as_str()).unwrap_or("?");
            println!("  🆔 {}: id={agent_id}, name={agent_name}", cfg.name);
        }
    }

    println!("\nCocoCat Core exiting.");
}
```

- [ ] **Step 2: Build and run**

```bash
cargo build
cargo run
```

- [ ] **Step 3: Commit**

```bash
git add src/main.rs
git commit -m "feat: add graceful error handling for multi-agent startup"
```

---

## Summary

After this phase:
- ✅ TOML config drives agent definitions
- ✅ Multiple agents spawn simultaneously
- ✅ Each agent knows its identity (id, name)
- ✅ Rust can find and communicate with any agent by id
- ✅ Graceful handling of partial failures

**Next possible phases:**
- Group chat (Rust message bus for inter-agent communication)
- Scene management
- Skill system
- Memory system (Dream/Consolidator)
