# Layer 1: Rust Core Engine Refactoring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Upgrade Rust core from prototype to Beta quality - eliminate panics, add timeouts/retries/logging/signals, split main.rs.

**Architecture:** Keep module boundaries, add errors.rs/logging.rs/signal.rs modules, strip main.rs.

**Tech Stack:** Rust (serde, toml, tracing crate)

---

### File Structure
- src/errors.rs [NEW] - Structured error types
- src/logging.rs [NEW] - tracing initialization
- src/signal.rs [NEW] - Signal handling
- src/hire.rs [NEW] - Extract hire logic from main.rs
- src/dispatcher.rs [NEW] - Extract dispatch logic from main.rs
- src/main.rs [MODIFY] - Reduced to ~150 lines
- src/agent_manager.rs [MODIFY] - Add timeout, safe unwrap
- src/agent_registry.rs [MODIFY] - Add retry backoff
- src/message_bus.rs [MODIFY] - Add error logging
- src/transport.rs [MODIFY] - Minor cleanup

## Task 1: Add tracing structured logging

**Files:**
- Create: `src/logging.rs`
- Modify: `Cargo.toml`
- Modify: `src/main.rs` (add mod and init call)

- [ ] **Step 1: Add tracing dependency to Cargo.toml**

Read the current Cargo.toml and replace its content with:

```toml
[package]
name = "cococat"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
toml = "0.8"
chrono = "0.4"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
```

- [ ] **Step 2: Create logging.rs**

Create `src/logging.rs`:

```rust
use tracing_subscriber::EnvFilter;

pub fn init() {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info"))
        )
        .init();
}
```

- [ ] **Step 3: Add logging module to main.rs and init at start**

Read `src/main.rs`. At line 4 (after `mod agent_registry;`), add:

```rust
mod logging;
```

Then in `fn main()`, at line 262 (after `println!("CocoCat Core starting...\n");` but before the directory creation), add:

```rust
    logging::init();
```

- [ ] **Step 4: Replace println! in main.rs with tracing calls**

Read `src/main.rs` and apply the following replacements:

**In `process_hire_requests` (lines 13-108):**

Replace line 47:
```
- println!("  Processing hire: {} ({})", new_name, new_id);
+ tracing::info!("Processing hire: {} ({})", new_name, new_id);
```

Replace line 58:
```
- println!("  Failed to update config: {e}");
+ tracing::warn!("Failed to update config: {e}");
```

Replace lines 93-94:
```
-             Ok(()) => println!("  {} ({}) hired and spawned", new_name, new_id),
-             Err(e) => println!("  Failed to spawn {}: {}", new_id, e),
+             Ok(()) => tracing::info!("{} ({}) hired and spawned", new_name, new_id),
+             Err(e) => tracing::error!("Failed to spawn {}: {}", new_id, e),
```

**In `check_user_questions` (lines 110-152):**

Replace line 128:
```
- println!("\n[Question] {}", q_text);
+ tracing::info!("[Question] {}", q_text);
```

Replace line 131:
```
- println!("  {}. {}", i + 1, opt);
+ tracing::info!("  {}. {}", i + 1, opt);
```

Keep lines 133, 134, 142, 143 (interactive print!) as-is — they are user-facing prompts, not logging.

Replace line 151:
```
- println!();
+ // (remove this line or keep as blank line)
```

**In `process_pending_hires` (lines 154-258):**

Replace lines 192-199 (the pending hire display block):
```
-         println!("\n--- Pending Hire ---");
-         println!("  Name:      {name}");
-         println!("  ID:        {id}");
-         println!("  Role:      {role}");
-         println!("  Scene:     {scene}");
-         println!("  Traits:    {traits}");
-         println!("  Objective: {objective}");
-         println!();
+         tracing::info!("--- Pending Hire ---");
+         tracing::info!("  Name:      {name}");
+         tracing::info!("  ID:        {id}");
+         tracing::info!("  Role:      {role}");
+         tracing::info!("  Scene:     {scene}");
+         tracing::info!("  Traits:    {traits}");
+         tracing::info!("  Objective: {objective}");
```

Replace lines 210-211:
```
-             println!("  Failed to serialize question: {e}");
-             continue;
+             tracing::warn!("Failed to serialize question: {e}");
+             continue;
```

Replace line 215:
```
-             println!("  Failed to write question: {e}");
+             tracing::warn!("Failed to write question: {e}");
```

Replace line 240:
```
-                         println!("  => Approved: {name} ({id})");
+                         tracing::info!("=> Approved: {name} ({id})");
```

Replace line 249:
```
-                         println!("  => Rejected: {name} ({id})");
+                         tracing::info!("=> Rejected: {name} ({id})");
```

**In `main` lines 260-418:**

Replace line 261:
```
- println!("CocoCat Core starting...\n");
+ println!("CocoCat Core starting...\n");  // Keep as println! (startup banner)
```

Replace line 272:
```
- println!("Loaded {} agent definitions\n", configs.len());
+ tracing::info!("Loaded {} agent definitions", configs.len());
```

Replace lines 276-277:
```
-         println!("  [{status}] {} ({})", cfg.name, cfg.id);
+         tracing::info!("  [{status}] {} ({})", cfg.name, cfg.id);
```

Replace line 279:
```
-     println!();
+     // blank line removed
```

Replace line 287:
```
- println!("Spawned {running} agents\n");
+ tracing::info!("Spawned {running} agents");
```

Replace lines 290-301 (Health Check section):
```
-     println!("--- Health Check ---");
-     for cfg in registry.configs.clone() {
...
-     println!();
+     tracing::info!("--- Health Check ---");
+     for cfg in registry.configs.clone() {
+         if !cfg.enabled { continue; }
+         let Some(agent) = registry.get(&cfg.id) else { continue; };
+         let ok = agent.call("ping", None, 0)
+             .ok()
+             .and_then(|r| r.result)
+             .map(|r| r.get("pong") == Some(&json!(true)))
+             .unwrap_or(false);
+         let status = if ok { "alive" } else { "dead" };
+         tracing::info!("  {} ({}) -> {}", cfg.name, cfg.id, status);
+     }
```

Replace lines 305-316 (Team Roster section):
```
-     println!("--- Team Roster ---");
-     for cfg in registry.configs.clone() {
...
-     println!();
+     tracing::info!("--- Team Roster ---");
+     for cfg in registry.configs.clone() {
+         if !cfg.enabled { continue; }
+         let Some(agent) = registry.get(&cfg.id) else { continue; };
+         if let Some(data) = agent.call("identify", None, 0).ok().and_then(|r| r.result) {
+             let name = data.get("name").and_then(|v| v.as_str()).unwrap_or("?");
+             let id = data.get("id").and_then(|v| v.as_str()).unwrap_or("?");
+             let scene = data.get("scene").and_then(|v| v.as_str()).unwrap_or("?");
+             tracing::info!("  {}: id={id}, name={name}, scene={scene}", cfg.id);
+         }
+     }
```

Replace line 319:
```
-     println!("--- Message Bus Demo ---");
+     tracing::info!("--- Message Bus Demo ---");
```

Replace lines 352-355:
```
-                     println!("\n  Leader completed in {iterations} iterations ({:.1}s):\n", elapsed.as_secs_f64());
-                     for line in content.lines() {
-                         println!("    {line}");
-                     }
+                     tracing::info!("Leader completed in {iterations} iterations ({:.1}s)", elapsed.as_secs_f64());
+                     for line in content.lines() {
+                         tracing::info!("  {line}");
+                     }
```

Replace line 364:
```
-                     println!("  Leader error [{}]: {}", err.code, err.message);
+                     tracing::warn!("Leader error [{}]: {}", err.code, err.message);
```

Replace line 368:
```
-                 println!("  Leader task failed: {e}");
+                 tracing::error!("Leader task failed: {e}");
```

Replace line 372:
```
-     println!();
+     // blank line removed
```

Replace line 375:
```
-     println!("--- Chat Log ---");
+     tracing::info!("--- Chat Log ---");
```

Replace lines 379-385:
```
-             let from = if msg.from == "system" { "●" } else { &msg.from };
-             let to = if msg.to == "*" { "team" } else { &msg.to };
-             println!("  [{from} -> {to}] {}", msg.content);
+             tracing::info!("  [{} -> {}] {}", msg.from, msg.to, msg.content);
```

Replace lines 386:
```
-     println!();
+     // blank line removed
```

Replace line 389:
```
-     println!("--- Entering Daemon Mode (type 'quit' or 'exit' to stop) ---");
+     tracing::info!("--- Entering Daemon Mode (type 'quit' or 'exit' to stop) ---");
```

Replace line 401:
```
-                 println!("  Health check: restarted {} agents", restarted.len());
+                 tracing::info!("Health check: restarted {} agents", restarted.len());
```

Replace lines 415-417:
```
-     println!("\nShutting down...");
-     message_bus::get_and_persist_counter();
-     println!("CocoCat Core exiting.");
+     tracing::info!("Shutting down...");
+     message_bus::get_and_persist_counter();
+     tracing::info!("CocoCat Core exiting.");
```

**In `check_and_process_dispatches` (lines 444-551):**

Replace line 500:
```
-         println!("  Routing dispatch to '{}'...", target_id);
+         tracing::info!("Routing dispatch to '{}'...", target_id);
```

Replace lines 503-506:
```
-                 println!("  \u{2705} Dispatch to '{}' succeeded", target_id);
-                 if let Some(ref result) = response.result {
-                     if let Some(content) = result["content"].as_str() {
-                         println!("  Response: {:.120}", content);
+                 tracing::info!("Dispatch to '{}' succeeded", target_id);
+                 if let Some(ref result) = response.result {
+                     if let Some(content) = result["content"].as_str() {
+                         tracing::info!("Response: {:.120}", content);
```

Replace line 518:
```
-                     println!("  \u{274C} Dispatch error [{}]: {}", err.code, err.message);
+                     tracing::warn!("Dispatch error [{}]: {}", err.code, err.message);
```

Replace line 531:
```
-                 println!("  \u{274C} Dispatch to '{}' failed: {}", target_id, e);
+                 tracing::error!("Dispatch to '{}' failed: {}", target_id, e);
```

- [ ] **Step 5: Build and verify**

Run: `cargo build 2>&1`
Expected: no errors

- [ ] **Step 6: Commit**

Note: do NOT commit unless the user asks. Just report the step.

## Task 2: Replace unwrap/expect with proper error handling

**Files:**
- Create: `src/errors.rs`
- Modify: `src/agent_manager.rs`
- Modify: `src/transport.rs`
- Modify: `src/main.rs`
- Modify: `src/lib.rs`

- [ ] **Step 1: Create errors.rs**

Create `src/errors.rs`:

```rust
use std::fmt;

#[derive(Debug)]
pub enum AgentError {
    IoError(std::io::Error),
    SerializationError(serde_json::Error),
    TransportError(String),
    AgentCrashed(String),
    Timeout(String),
    StdinClosed(String),
    StdoutClosed(String),
    ConfigError(String),
}

impl fmt::Display for AgentError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AgentError::IoError(e) => write!(f, "IO error: {e}"),
            AgentError::SerializationError(e) => write!(f, "Serialization error: {e}"),
            AgentError::TransportError(e) => write!(f, "Transport error: {e}"),
            AgentError::AgentCrashed(msg) => write!(f, "Agent crashed: {msg}"),
            AgentError::Timeout(msg) => write!(f, "Timeout: {msg}"),
            AgentError::StdinClosed(msg) => write!(f, "Stdin closed: {msg}"),
            AgentError::StdoutClosed(msg) => write!(f, "Stdout closed: {msg}"),
            AgentError::ConfigError(msg) => write!(f, "Config error: {msg}"),
        }
    }
}

impl std::error::Error for AgentError {}

impl From<std::io::Error> for AgentError {
    fn from(e: std::io::Error) -> Self {
        AgentError::IoError(e)
    }
}

impl From<serde_json::Error> for AgentError {
    fn from(e: serde_json::Error) -> Self {
        AgentError::SerializationError(e)
    }
}
```

Add `mod errors;` to `src/lib.rs`:

```rust
pub mod transport;
pub mod message_bus;
pub mod errors;
```

- [ ] **Step 2: Update transport.rs to use AgentError**

Replace the content of `src/transport.rs` to change return types from `Result<..., String>` to `Result<..., crate::errors::AgentError>`:

```rust
use crate::errors::AgentError;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{BufRead, Write};

#[derive(Debug, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub params: Option<Value>,
    pub id: u64,
}

impl JsonRpcRequest {
    pub fn new(method: &str, params: Option<Value>, id: u64) -> Self {
        Self {
            jsonrpc: "2.0".to_string(),
            method: method.to_string(),
            params,
            id,
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<u64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
}

pub fn send_request(writer: &mut impl Write, req: &JsonRpcRequest) -> Result<(), AgentError> {
    let line = serde_json::to_string(req)?;
    writeln!(writer, "{}", line)?;
    writer.flush()?;
    Ok(())
}

pub fn read_response(reader: &mut impl BufRead) -> Result<JsonRpcResponse, AgentError> {
    let mut line = String::new();
    reader.read_line(&mut line)?;
    if line.is_empty() {
        return Err(AgentError::StdoutClosed("EOF: child process closed stdout".to_string()));
    }
    let resp: JsonRpcResponse = serde_json::from_str(&line)?;
    Ok(resp)
}
```

- [ ] **Step 3: Rewrite agent_manager.rs with AgentError**

Replace the content of `src/agent_manager.rs`:

```rust
use crate::errors::AgentError;
use crate::transport::{self, JsonRpcRequest, JsonRpcResponse};
use std::io::BufReader;
use std::process::{Child, ChildStdin, Command, Stdio};

pub struct AgentProcess {
    child: Child,
    stdin_writer: Option<ChildStdin>,
    stdout_reader: Option<BufReader<std::process::ChildStdout>>,
    interpreter: String,
}

#[allow(dead_code)]
impl AgentProcess {
    pub fn spawn(
        interpreter: &str,
        python_script_path: &str,
        extra_args: &[&str],
    ) -> Result<Self, AgentError> {
        let mut cmd = Command::new(interpreter);
        cmd.arg("-u").arg(python_script_path);
        for arg in extra_args {
            cmd.arg(arg);
        }
        let mut child = cmd
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;

        let stdin_writer = child.stdin.take()
            .ok_or_else(|| AgentError::StdinClosed("failed to open agent stdin".to_string()))?;
        let stdout_reader = child.stdout.take()
            .ok_or_else(|| AgentError::StdoutClosed("failed to open agent stdout".to_string()))?;

        Ok(Self {
            child,
            stdin_writer: Some(stdin_writer),
            stdout_reader: Some(BufReader::new(stdout_reader)),
            interpreter: interpreter.to_string(),
        })
    }

    pub fn call(
        &mut self,
        method: &str,
        params: Option<serde_json::Value>,
        id: u64,
    ) -> Result<JsonRpcResponse, AgentError> {
        let writer = self.stdin_writer.as_mut()
            .ok_or_else(|| AgentError::StdinClosed("stdin not available".to_string()))?;
        let req = JsonRpcRequest::new(method, params, id);
        transport::send_request(writer, &req)?;
        let reader = self.stdout_reader.as_mut()
            .ok_or_else(|| AgentError::StdoutClosed("stdout not available".to_string()))?;
        transport::read_response(reader)
    }

    pub fn is_running(&mut self) -> bool {
        match self.child.try_wait() {
            Ok(None) => true,
            _ => false,
        }
    }

    pub fn kill(&mut self) -> Result<(), AgentError> {
        self.child.kill()?;
        Ok(())
    }

    pub fn wait(&mut self) -> Result<(), AgentError> {
        drop(self.stdin_writer.take());
        self.child.wait()?;
        Ok(())
    }
}

impl Drop for AgentProcess {
    fn drop(&mut self) {
        drop(self.stdin_writer.take());
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
```

- [ ] **Step 4: Fix main.rs unwraps**

In `src/main.rs`, find the two `serde_json::to_string_pretty(...).unwrap()` calls:

**Line 78** (inside process_hire_requests):
```
-                 let _ = fs::write(&profile_path, serde_json::to_string_pretty(&profile).unwrap());
+                 match serde_json::to_string_pretty(&profile) {
+                     Ok(s) => {
+                         if let Err(e) = fs::write(&profile_path, s) {
+                             tracing::warn!("Failed to write profile to {}: {e}", profile_path);
+                         }
+                     }
+                     Err(e) => tracing::warn!("Failed to serialize profile for {}: {e}", new_id),
+                 }
```

**Line 150** (inside check_user_questions):
```
-     let _ = std::fs::write(question_path, serde_json::to_string_pretty(&response).unwrap());
+     match serde_json::to_string_pretty(&response) {
+         Ok(s) => {
+             if let Err(e) = std::fs::write(question_path, s) {
+                 tracing::warn!("Failed to write answer to {}: {e}", question_path.display());
+             }
+         }
+         Err(e) => tracing::warn!("Failed to serialize answer response: {e}"),
+     }
```

Also update the `expect` on line 271 for the AgentRegistry::load_config call:
```
-         .expect("failed to load agent config")
+         .expect("Failed to load agent config from agents/config.toml — is the file missing or malformed?")
```

- [ ] **Step 5: Build**

Run: `cargo build 2>&1`
Fix any compile errors.

## Task 3: Add agent call timeout

**Files:**
- Modify: `src/agent_manager.rs`

- [ ] **Step 1: Add timeout to AgentProcess::call()**

Read `src/agent_manager.rs` and replace the `call` method with a version that uses a read thread and recv_timeout.

First, update the struct to track the agent ID for better error messages:

```rust
pub struct AgentProcess {
    child: Child,
    stdin_writer: Option<ChildStdin>,
    stdout_reader: Option<BufReader<std::process::ChildStdout>>,
    interpreter: String,
    agent_id: String,  // NEW
}
```

Update the spawn method to set the agent_id. Change the signature to accept an agent_id:

```rust
    pub fn spawn(
        interpreter: &str,
        python_script_path: &str,
        extra_args: &[&str],
        agent_id: &str,
    ) -> Result<Self, AgentError> {
        let mut cmd = Command::new(interpreter);
        cmd.arg("-u").arg(python_script_path);
        for arg in extra_args {
            cmd.arg(arg);
        }
        let mut child = cmd
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;

        let stdin_writer = child.stdin.take()
            .ok_or_else(|| AgentError::StdinClosed("failed to open agent stdin".to_string()))?;
        let stdout_reader = child.stdout.take()
            .ok_or_else(|| AgentError::StdoutClosed("failed to open agent stdout".to_string()))?;

        Ok(Self {
            child,
            stdin_writer: Some(stdin_writer),
            stdout_reader: Some(BufReader::new(stdout_reader)),
            interpreter: interpreter.to_string(),
            agent_id: agent_id.to_string(),
        })
    }
```

Now replace the `call` method with a timeout-aware version:

```rust
    pub fn call(
        &mut self,
        method: &str,
        params: Option<serde_json::Value>,
        id: u64,
        timeout_secs: u64,
    ) -> Result<JsonRpcResponse, AgentError> {
        let writer = self.stdin_writer.as_mut()
            .ok_or_else(|| AgentError::StdinClosed("stdin not available for agent {}".to_string()))?;
        let req = JsonRpcRequest::new(method, params, id);
        transport::send_request(writer, &req)?;

        let reader = self.stdout_reader.take()
            .ok_or_else(|| AgentError::StdoutClosed("stdout not available for agent".to_string()))?;

        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            let result = transport::read_response(&mut &reader);
            let _ = tx.send((reader, result));
        });

        let timeout = std::time::Duration::from_secs(timeout_secs);
        match rx.recv_timeout(timeout) {
            Ok((reader, Ok(response))) => {
                self.stdout_reader = Some(reader);
                Ok(response)
            }
            Ok((reader, Err(e))) => {
                self.stdout_reader = Some(reader);
                Err(e)
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                Err(AgentError::Timeout(format!(
                    "agent '{}' call to '{}' timed out after {}s",
                    self.agent_id, method, timeout_secs
                )))
            }
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                Err(AgentError::AgentCrashed(format!(
                    "reader thread for agent '{}' disconnected",
                    self.agent_id
                )))
            }
        }
    }
```

- [ ] **Step 2: Update agent_registry.rs to match new spawn and call signatures**

Read `src/agent_registry.rs`. Update `start_all` and `start_one` to pass `agent_id` to `AgentProcess::spawn`.

In `start_all` (line 55):
```
-             let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra_args)?;
+             let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra_args, &config.id)?;
```

In `start_one` (line 66):
```
-         let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra)?;
+         let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra, &config.id)?;
```

In `dispatch_message` (line 171), the `agent.call(...)` call needs a `timeout_secs` parameter:
```
-         agent.call(method, params, 0)
+         agent.call(method, params, 0, 60)
```

- [ ] **Step 3: Update main.rs call sites with timeout_secs parameter**

In `src/main.rs`, find all `agent.call(` invocations and add a `timeout_secs` argument:

Line 294 (health check ping):
```
-         let ok = agent.call("ping", None, 0)
+         let ok = agent.call("ping", None, 0, 10)
```

Line 309 (identify):
```
-         if let Some(data) = agent.call("identify", None, 0).ok().and_then(|r| r.result) {
+         if let Some(data) = agent.call("identify", None, 0, 10).ok().and_then(|r| r.result) {
```

Line 339 (leader task):
```
-             match agent.call("task", Some(params), 1) {
+             match agent.call("task", Some(params), 1, 120) {
```

- [ ] **Step 4: Build**

Run: `cargo build 2>&1`
Fix any compile errors.

## Task 4: Add health check retry backoff

**Files:**
- Modify: `src/agent_registry.rs`

- [ ] **Step 1: Add RestartState struct and backoff logic**

Read `src/agent_registry.rs` and add the following after the `AgentConfig` struct:

```rust
use std::collections::HashMap;
use std::time::Instant;

struct RestartState {
    retry_count: u32,
    backoff_until: Instant,
    consecutive_successes: u32,
}
```

Add a `restart_states` field to `AgentRegistry`:

```rust
pub struct AgentRegistry {
    pub configs: Vec<AgentConfig>,
    pub processes: HashMap<String, AgentProcess>,
    restart_states: HashMap<String, RestartState>,
}
```

Initialize it in `new`:

```rust
    pub fn new(configs: Vec<AgentConfig>) -> Self {
        Self {
            configs,
            processes: HashMap::new(),
            restart_states: HashMap::new(),
        }
    }
```

Add a `remove_dead` that also cleans up the restart state:

```rust
    fn remove_dead(&mut self, id: &str) {
        self.processes.remove(id);
        self.restart_states.remove(id);
    }
```

Replace the `health_check` method:

```rust
    pub fn health_check(&mut self) -> Vec<String> {
        let mut restarted = Vec::new();
        let ids: Vec<String> = self.processes.keys().cloned().collect();
        for id in ids {
            let running = self.processes.get_mut(&id)
                .map(|p| p.is_running())
                .unwrap_or(false);
            if !running {
                self.processes.remove(&id);
                let now = Instant::now();
                let should_restart = match self.restart_states.get(&id) {
                    Some(state) if now < state.backoff_until => {
                        tracing::debug!("Agent '{}' in backoff until {:?}, skipping", id, state.backoff_until);
                        false
                    }
                    _ => true,
                };
                if !should_restart {
                    continue;
                }
                tracing::info!("Agent '{}' is dead, restarting...", id);
                match self.restart_one(&id) {
                    Ok(()) => {
                        tracing::info!("Agent '{}' restarted successfully", id);
                        let state = self.restart_states.entry(id.clone()).or_insert(RestartState {
                            retry_count: 0,
                            backoff_until: now,
                            consecutive_successes: 0,
                        });
                        state.consecutive_successes = 0;
                        restarted.push(id);
                    }
                    Err(e) => {
                        tracing::error!("Failed to restart agent '{}': {}", id, e);
                        let state = self.restart_states.entry(id.clone()).or_insert(RestartState {
                            retry_count: 0,
                            backoff_until: now,
                            consecutive_successes: 0,
                        });
                        state.retry_count += 1;
                        let backoff_secs = std::cmp::min(2u64.pow(state.retry_count) * 5, 300);
                        state.backoff_until = now + std::time::Duration::from_secs(backoff_secs);
                        tracing::warn!("Agent '{}' restart backoff set to {}s (retry #{})", id, backoff_secs, state.retry_count);
                    }
                }
            } else {
                if let Some(state) = self.restart_states.get_mut(&id) {
                    state.consecutive_successes += 1;
                    if state.consecutive_successes >= 3 && state.retry_count > 0 {
                        tracing::info!("Agent '{}' healthy for {} checks, resetting retry count", id, state.consecutive_successes);
                        state.retry_count = 0;
                        state.consecutive_successes = 0;
                    }
                }
            }
        }
        restarted
    }
```

- [ ] **Step 2: Build**

Run: `cargo build 2>&1`
Fix any compile errors.

## Task 5: Signal handling

**Files:**
- Create: `src/signal.rs`
- Modify: `src/main.rs`

- [ ] **Step 1: Create signal.rs**

Create `src/signal.rs`:

```rust
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

pub fn setup() -> Arc<AtomicBool> {
    let shutdown = Arc::new(AtomicBool::new(false));
    let s = shutdown.clone();
    std::thread::spawn(move || {
        let mut input = String::new();
        while s.load(Ordering::Relaxed) {
            input.clear();
            match std::io::stdin().read_line(&mut input) {
                Ok(_) => {
                    let trimmed = input.trim();
                    if trimmed.eq_ignore_ascii_case("quit") || trimmed.eq_ignore_ascii_case("exit") {
                        s.store(false, Ordering::Relaxed);
                        break;
                    }
                }
                Err(_) => {
                    s.store(false, Ordering::Relaxed);
                    break;
                }
            }
        }
    });
    shutdown
}
```

- [ ] **Step 2: Modify main.rs to use signal.rs**

In `src/main.rs`, after the other `mod` declarations, add:

```rust
mod signal;
```

Replace the `setup_shutdown_handler` function and its call in `main()`:

Remove lines 420-441 (`fn setup_shutdown_handler`).

Replace line 391-392:
```
-     let running = Arc::new(AtomicBool::new(true));
-     setup_shutdown_handler(running.clone());
+     let running = signal::setup();
```

Also remove the unused `AtomicBool` import from the `use` statement at line 9. Change:
```
- use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
+ use std::sync::atomic::{AtomicU64, Ordering};
```

- [ ] **Step 3: Build**

Run: `cargo build 2>&1`
Fix any compile errors.

## Task 6: Split main.rs

**Files:**
- Create: `src/hire.rs`
- Create: `src/dispatcher.rs`
- Modify: `src/main.rs`

- [ ] **Step 1: Create hire.rs**

Create `src/hire.rs` with the hire-related functions extracted from main.rs:

```rust
use crate::agent_registry::{AgentConfig, AgentRegistry};
use crate::message_bus;
use serde_json::json;
use std::fs;

pub fn process_hire_requests(registry: &mut AgentRegistry) {
    let hire_dir = std::path::Path::new("agents/hire_requests/approved");
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

        tracing::info!("Processing hire: {} ({})", new_name, new_id);

        let config_path = "agents/config.toml";
        let mut config_content = fs::read_to_string(config_path).unwrap_or_default();
        let new_entry = format!(
            "\n[[agents]]\nid = \"{}\"\nname = \"{}\"\ninterpreter = \"python\"\nscript = \"py-agent/agent_runtime.py\"\nenabled = true\nscene = \"default\"\n",
            new_id, new_name
        );
        config_content.push_str(&new_entry);
        if let Err(e) = fs::write(config_path, &config_content) {
            tracing::warn!("Failed to update config: {e}");
            continue;
        }

        let mem_dir = format!("agents/{}/memory", new_id);
        if let Err(e) = fs::create_dir_all(&mem_dir) {
            tracing::warn!("Failed to create memory dir {}: {e}", mem_dir);
        }
        if let Err(e) = fs::write(format!("{}/MEMORY.md", mem_dir), format!("# {} Memory\n\nPersonal memories and learnings.\n", new_name)) {
            tracing::warn!("Failed to write MEMORY.md: {e}");
        }
        if let Err(e) = fs::write(format!("{}/history.jsonl", mem_dir), "") {
            tracing::warn!("Failed to write history.jsonl: {e}");
        }
        if let Err(e) = fs::write(format!("{}/.dream_cursor", mem_dir), "0") {
            tracing::warn!("Failed to write .dream_cursor: {e}");
        }

        let profile_path = format!("agents/{}/profile.json", new_id);
        if !std::path::Path::new(&profile_path).exists() {
            if let Some(p) = hire.get("profile") {
                let mut profile = p.clone();
                if profile.get("gender").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
                    let gender = if new_id.as_bytes().iter().sum::<u8>() % 2 == 0 { "male" } else { "female" };
                    profile["gender"] = serde_json::json!(gender);
                }
                match serde_json::to_string_pretty(&profile) {
                    Ok(s) => {
                        if let Err(e) = fs::write(&profile_path, s) {
                            tracing::warn!("Failed to write profile to {}: {e}", profile_path);
                        }
                    }
                    Err(e) => tracing::warn!("Failed to serialize profile for {}: {e}", new_id),
                }
            }
        }

        let new_config = AgentConfig {
            id: new_id.clone(),
            name: new_name.clone(),
            interpreter: "python".to_string(),
            script: "py-agent/agent_runtime.py".to_string(),
            enabled: true,
            scene: Some("default".to_string()),
        };
        registry.configs.push(new_config.clone());
        match registry.start_one(new_config) {
            Ok(()) => tracing::info!("{} ({}) hired and spawned", new_name, new_id),
            Err(e) => tracing::error!("Failed to spawn {}: {}", new_id, e),
        }

        let _ = message_bus::log_message(&message_bus::new_message(
            "system".to_string(),
            "*".to_string(),
            format!("New team member: {} ({})", new_name, new_id),
            "system".to_string(),
        ));

        let _ = fs::remove_file(&path);
    }
}

pub fn process_pending_hires() {
    let pending_dir = std::path::Path::new("agents/hire_requests/pending");
    if !pending_dir.exists() {
        return;
    }

    let entries = match fs::read_dir(pending_dir) {
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

        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let req: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("unknown");
        let id = req.get("id").and_then(|v| v.as_str()).unwrap_or("unknown");
        let role = req.get("profile").and_then(|p| p.get("role")).and_then(|v| v.as_str()).unwrap_or("N/A");
        let scene = req.get("scene").and_then(|v| v.as_str()).unwrap_or("N/A");
        let traits = req.get("profile").and_then(|p| p.get("traits")).and_then(|v| v.as_array()).map(|a| {
            a.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join(", ")
        }).unwrap_or_default();
        let objective = req.get("profile").and_then(|p| p.get("objective")).and_then(|v| v.as_str()).unwrap_or("N/A");

        tracing::info!("--- Pending Hire ---");
        tracing::info!("  Name:      {name}");
        tracing::info!("  ID:        {id}");
        tracing::info!("  Role:      {role}");
        tracing::info!("  Scene:     {scene}");
        tracing::info!("  Traits:    {traits}");
        tracing::info!("  Objective: {objective}");

        let question_path = std::path::Path::new("agents/_ask_user.json");
        let question = json!({
            "question": format!("Process hire request for '{}' ({})", name, id),
            "options": ["Approve", "Modify and Approve", "Reject"],
            "status": "pending"
        });
        let question_str = match serde_json::to_string_pretty(&question) {
            Ok(s) => s,
            Err(e) => {
                tracing::warn!("Failed to serialize question: {e}");
                continue;
            }
        };
        if let Err(e) = fs::write(question_path, question_str) {
            tracing::warn!("Failed to write question: {e}");
            continue;
        }

        loop {
            std::thread::sleep(std::time::Duration::from_millis(500));
            let answer_content = match fs::read_to_string(question_path) {
                Ok(c) => c,
                Err(_) => continue,
            };
            let answer_json: serde_json::Value = match serde_json::from_str(&answer_content) {
                Ok(v) => v,
                Err(_) => continue,
            };
            if answer_json.get("status").and_then(|v| v.as_str()) == Some("answered") {
                let answer = answer_json.get("answer").and_then(|v| v.as_str()).unwrap_or("").to_string();

                match answer.as_str() {
                    "Approve" | "Modify and Approve" => {
                        let approved_dir = std::path::Path::new("agents/hire_requests/approved");
                        let _ = fs::create_dir_all(approved_dir);
                        let dest = approved_dir.join(path.file_name().unwrap());
                        let _ = fs::rename(&path, &dest);
                        let marker_path = format!("{}.processed", dest.display());
                        let _ = fs::write(&marker_path, "{}");
                        tracing::info!("=> Approved: {name} ({id})");
                    }
                    _ => {
                        let rejected_dir = std::path::Path::new("agents/hire_requests/rejected");
                        let _ = fs::create_dir_all(rejected_dir);
                        let dest = rejected_dir.join(path.file_name().unwrap());
                        let _ = fs::rename(&path, &dest);
                        let marker_path = format!("{}.processed", dest.display());
                        let _ = fs::write(&marker_path, "{}");
                        tracing::info!("=> Rejected: {name} ({id})");
                    }
                }

                let _ = fs::remove_file(question_path);
                break;
            }
        }
    }
}

pub fn check_user_questions() {
    let question_path = std::path::Path::new("agents/_ask_user.json");
    if !question_path.exists() {
        return;
    }
    let content = match std::fs::read_to_string(question_path) {
        Ok(c) => c,
        Err(_) => return,
    };
    let question: serde_json::Value = match serde_json::from_str(&content) {
        Ok(v) => v,
        Err(_) => return,
    };
    let q_text = question.get("question").and_then(|v| v.as_str()).unwrap_or("?").to_string();
    let options: Vec<String> = question.get("options").and_then(|v| v.as_array()).map(|a| {
        a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect()
    }).unwrap_or_default();

    tracing::info!("[Question] {}", q_text);
    let answer = if !options.is_empty() {
        for (i, opt) in options.iter().enumerate() {
            println!("  {}. {}", i + 1, opt);
        }
        print!("Enter choice (1-{}): ", options.len());
        let _ = std::io::Write::flush(&mut std::io::stdout());
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).ok();
        let input = input.trim().to_string();
        if let Ok(idx) = input.parse::<usize>() {
            if idx >= 1 && idx <= options.len() { options[idx - 1].clone() } else { input }
        } else { input }
    } else {
        print!("Your answer: ");
        let _ = std::io::Write::flush(&mut std::io::stdout());
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).ok();
        input.trim().to_string()
    };

    let response = serde_json::json!({"question": q_text, "answer": answer, "status": "answered"});
    match serde_json::to_string_pretty(&response) {
        Ok(s) => {
            if let Err(e) = std::fs::write(question_path, s) {
                tracing::warn!("Failed to write answer to {}: {e}", question_path.display());
            }
        }
        Err(e) => tracing::warn!("Failed to serialize answer response: {e}"),
    }
    println!();
}
```

- [ ] **Step 2: Create dispatcher.rs**

Create `src/dispatcher.rs` with the dispatch-related functions extracted from main.rs:

```rust
use crate::agent_registry::AgentRegistry;
use crate::message_bus;
use std::fs;
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT_TASK_ID: AtomicU64 = AtomicU64::new(1);

pub fn check_and_process_dispatches(registry: &mut AgentRegistry) {
    let dispatch_dir = std::path::Path::new("agents/dispatch_queue");
    if !dispatch_dir.exists() {
        return;
    }

    let entries = match std::fs::read_dir(dispatch_dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    let mut processed = Vec::new();

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

        let target_id = dispatch.get("target_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let method = dispatch.get("method").and_then(|v| v.as_str()).unwrap_or("task").to_string();
        let params = dispatch.get("params").cloned();
        let prompt = params.as_ref()
            .and_then(|p| p.get("prompt"))
            .and_then(|p| p.as_str())
            .unwrap_or("")
            .to_string();

        if target_id.is_empty() {
            continue;
        }

        let task_id = NEXT_TASK_ID.fetch_add(1, Ordering::Relaxed);

        message_bus::log_message(&message_bus::ChatMessage {
            task_id: Some(task_id),
            ..message_bus::new_message(
                "leader".to_string(),
                target_id.clone(),
                format!("Dispatching task: {:.80}", prompt),
                "task".to_string(),
            )
        }).ok();

        tracing::info!("Routing dispatch to '{}'...", target_id);
        match registry.dispatch_message(&target_id, &method, params) {
            Ok(response) => {
                tracing::info!("Dispatch to '{}' succeeded", target_id);
                if let Some(ref result) = response.result {
                    if let Some(content) = result["content"].as_str() {
                        tracing::info!("Response: {:.120}", content);
                        message_bus::log_message(&message_bus::ChatMessage {
                            task_id: Some(task_id),
                            ..message_bus::new_message(
                                target_id.clone(),
                                "leader".to_string(),
                                content.to_string(),
                                "reply".to_string(),
                            )
                        }).ok();
                    }
                } else if let Some(ref err) = response.error {
                    tracing::warn!("Dispatch error [{}]: {}", err.code, err.message);
                    message_bus::log_message(&message_bus::ChatMessage {
                        task_id: Some(task_id),
                        ..message_bus::new_message(
                            target_id.clone(),
                            "leader".to_string(),
                            format!("Error [{}]: {}", err.code, err.message),
                            "reply".to_string(),
                        )
                    }).ok();
                }
            }
            Err(e) => {
                tracing::error!("Dispatch to '{}' failed: {}", target_id, e);
                message_bus::log_message(&message_bus::ChatMessage {
                    task_id: Some(task_id),
                    ..message_bus::new_message(
                        "system".to_string(),
                        "leader".to_string(),
                        format!("Dispatch to {} failed: {}", target_id, e),
                        "system".to_string(),
                    )
                }).ok();
            }
        }

        processed.push(path);
    }

    for path in processed {
        let _ = std::fs::remove_file(&path);
    }
}
```

- [ ] **Step 3: Add mod declarations in main.rs**

Add after the other `mod` declarations in main.rs:

```rust
mod hire;
mod dispatcher;
mod signal;
mod logging;
```

Replace the function calls in main.rs to use the new modules. For example:

`process_hire_requests(&mut registry);` becomes `hire::process_hire_requests(&mut registry);`

`process_pending_hires();` becomes `hire::process_pending_hires();`

`check_user_questions();` becomes `hire::check_user_questions();`

`check_and_process_dispatches(&mut registry);` becomes `dispatcher::check_and_process_dispatches(&mut registry);`

- [ ] **Step 4: Slim down main.rs to ~150 lines**

After all extractions, `src/main.rs` should contain only:

```rust
use cococat::transport;
use cococat::message_bus;
mod agent_manager;
mod agent_registry;
mod hire;
mod dispatcher;
mod signal;
mod logging;

use agent_registry::AgentRegistry;
use serde_json::json;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

fn main() {
    println!("CocoCat Core starting...\n");
    logging::init();

    let _ = std::fs::create_dir_all("chat");
    let _ = std::fs::create_dir_all("agents/dispatch_queue");
    let _ = std::fs::create_dir_all("agents/dispatch_messages");

    message_bus::init_counter();

    let configs = AgentRegistry::load_config("agents/config.toml")
        .expect("Failed to load agent config from agents/config.toml — is the file missing or malformed?");
    tracing::info!("Loaded {} agent definitions", configs.len());

    for cfg in &configs {
        let status = if cfg.enabled { "enabled" } else { "disabled" };
        tracing::info!("  [{status}] {} ({})", cfg.name, cfg.id);
    }

    let mut registry = AgentRegistry::new(configs);
    match registry.start_all() {
        Ok(()) => {}
        Err(e) => eprintln!("Warning: some agents failed to spawn: {e}"),
    }

    let running = registry.status().iter().filter(|s| s.running).count();
    tracing::info!("Spawned {running} agents");

    tracing::info!("--- Health Check ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        let ok = agent.call("ping", None, 0, 10)
            .ok()
            .and_then(|r| r.result)
            .map(|r| r.get("pong") == Some(&json!(true)))
            .unwrap_or(false);
        let status = if ok { "alive" } else { "dead" };
        tracing::info!("  {} ({}) -> {}", cfg.name, cfg.id, status);
    }

    tracing::info!("--- Team Roster ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        if let Some(data) = agent.call("identify", None, 0, 10).ok().and_then(|r| r.result) {
            let name = data.get("name").and_then(|v| v.as_str()).unwrap_or("?");
            let id = data.get("id").and_then(|v| v.as_str()).unwrap_or("?");
            let scene = data.get("scene").and_then(|v| v.as_str()).unwrap_or("?");
            tracing::info!("  {}: id={id}, name={name}, scene={scene}", cfg.id);
        }
    }

    tracing::info!("--- Message Bus Demo ---");

    message_bus::log_message(&message_bus::new_message(
        "system".to_string(),
        "*".to_string(),
        "Team online. Message bus active.".to_string(),
        "system".to_string(),
    )).ok();

    if let Some(agent) = registry.get("leader") {
        let prompt = concat!(
            "You are the team leader (组长). Your team: employee_a (员工A) and employee_b (员工B).\n\n",
            "Use your dispatch_task tool to send this EXACT message to employee_a:\n",
            "\"Hello 员工A, this is a test message from the group chat. Please confirm you received this by responding with 'Message received by employee_a'.\"\n\n",
            "After using dispatch_task, tell me what you did."
        );
        let params = json!({"prompt": prompt});
        let start = Instant::now();
        match agent.call("task", Some(params), 1, 120) {
            Ok(resp) => {
                let elapsed = start.elapsed();
                message_bus::log_message(&message_bus::new_message(
                    "leader".to_string(),
                    "*".to_string(),
                    format!("Task completed in {:.1}s", elapsed.as_secs_f64()),
                    "system".to_string(),
                )).ok();

                if let Some(ref result) = resp.result {
                    let content = result["content"].as_str().unwrap_or("(no content)");
                    let iterations = result["iterations"].as_u64().unwrap_or(0);
                    tracing::info!("Leader completed in {iterations} iterations ({:.1}s)", elapsed.as_secs_f64());
                    for line in content.lines() {
                        tracing::info!("  {line}");
                    }

                    dispatcher::check_and_process_dispatches(&mut registry);
                    hire::process_pending_hires();
                    hire::process_hire_requests(&mut registry);
                    hire::check_user_questions();
                } else if let Some(ref err) = resp.error {
                    tracing::warn!("Leader error [{}]: {}", err.code, err.message);
                }
            }
            Err(e) => {
                tracing::error!("Leader task failed: {e}");
            }
        }
    }

    tracing::info!("--- Chat Log ---");
    match message_bus::read_recent(20) {
        Ok(messages) => {
            for msg in &messages {
                tracing::info!("  [{} -> {}] {}", msg.from, msg.to, msg.content);
            }
        }
        Err(e) => tracing::warn!("Failed to read chat log: {e}"),
    }

    tracing::info!("--- Entering Daemon Mode (type 'quit' or 'exit' to stop) ---");

    let running = signal::setup();
    let mut last_health_check = Instant::now();
    let health_check_interval = std::time::Duration::from_secs(15);

    while running.load(std::sync::atomic::Ordering::Relaxed) {
        if last_health_check.elapsed() >= health_check_interval {
            let restarted = registry.health_check();
            if !restarted.is_empty() {
                tracing::info!("Health check: restarted {} agents", restarted.len());
            }
            last_health_check = Instant::now();
        }

        dispatcher::check_and_process_dispatches(&mut registry);
        hire::process_pending_hires();
        hire::process_hire_requests(&mut registry);
        hire::check_user_questions();
        message_bus::get_and_persist_counter();

        std::thread::sleep(std::time::Duration::from_secs(5));
    }

    tracing::info!("Shutting down...");
    message_bus::get_and_persist_counter();
    tracing::info!("CocoCat Core exiting.");
}
```

- [ ] **Step 5: Build**

Run: `cargo build 2>&1`
Fix any compile errors.

## Task 7: Replace swallowed errors with tracing

**Files:**
- Modify: `src/message_bus.rs`
- Modify: `src/agent_registry.rs`
- Modify: `src/main.rs`
- Modify: `src/hire.rs`
- Modify: `src/dispatcher.rs`

- [ ] **Step 1: Fix message_bus.rs swallowed errors**

In `src/message_bus.rs`, replace line 15 (`let _ = std::fs::write(...)`) with:

```rust
fn save_counter(val: u64) {
    if let Err(e) = std::fs::write("chat/.counter", val.to_string()) {
        tracing::warn!("Failed to save message counter: {e}");
    }
}
```

Replace line 165 (inside `dispatch_message` in agent_registry.rs, but the plan says message_bus.rs — actually line 165 of agent_registry.rs has `let _ = writeln!`). Let me fix both message_bus.rs and agent_registry.rs.

In `src/message_bus.rs`, the `log_message` function uses `unwrap_or_default()` on line 36:

```rust
    let existing = std::fs::read_to_string(chat_path).unwrap_or_default();
```

Replace with:

```rust
    let existing = match std::fs::read_to_string(chat_path) {
        Ok(s) => s,
        Err(_) => {
            tracing::debug!("Chat log does not exist yet, starting fresh");
            String::new()
        }
    };
```

- [ ] **Step 2: Fix agent_registry.rs swallowed errors**

In `src/agent_registry.rs`, find the `dispatch_message` method and replace the `let _ = writeln!` with:

```rust
                if let Err(e) = writeln!(file, "{}", msg_content) {
                    tracing::warn!("Failed to write dispatch message for '{}': {e}", target_id);
                }
```

- [ ] **Step 3: Fix main.rs / hire.rs / dispatcher.rs swallowed errors**

In `src/main.rs` (after Task 6 extraction, the remaining file), replace each `let _ =` with proper tracing:

Lines with `let _ = std::fs::create_dir_all(...)` at the top of main:
```rust
    for dir in &["chat", "agents/dispatch_queue", "agents/dispatch_messages"] {
        if let Err(e) = std::fs::create_dir_all(dir) {
            tracing::warn!("Failed to create directory {}: {e}", dir);
        }
    }
```

Lines with `.ok()` pattern:
```rust
    if let Err(e) = message_bus::log_message(&message_bus::new_message(...)) {
        tracing::warn!("Failed to log message: {e}");
    }
```

In `src/hire.rs`, replace `let _ = fs::remove_file(&path);` with:
```rust
    if let Err(e) = fs::remove_file(&path) {
        tracing::warn!("Failed to remove approved hire file {}: {e}", path.display());
    }
```

Replace `let _ = message_bus::log_message(...)` patterns:
```rust
    let log_result = message_bus::log_message(&message_bus::new_message(
        "system".to_string(),
        "*".to_string(),
        format!("New team member: {} ({})", new_name, new_id),
        "system".to_string(),
    ));
    if let Err(e) = log_result {
        tracing::warn!("Failed to log hire message: {e}");
    }
```

Replace `let _ = fs::create_dir_all(...)` patterns in `process_pending_hires`:
```rust
                if let Err(e) = fs::create_dir_all(approved_dir) {
                    tracing::warn!("Failed to create approved dir: {e}");
                }
```

Same pattern for rejected dir, rename, write, remove_file calls.

In `src/dispatcher.rs`, replace:
```rust
    for path in processed {
        if let Err(e) = std::fs::remove_file(&path) {
            tracing::warn!("Failed to remove dispatch file {}: {e}", path.display());
        }
    }
```

Replace `.ok()` on log_message calls with proper `if let Err(e)` blocks.

- [ ] **Step 4: Build**

Run: `cargo build 2>&1`
Fix any compile errors.
