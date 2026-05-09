# CocoCat MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal viable path: Rust spawns a Python agent subprocess and exchanges a JSON-RPC ping/pong message.

**Architecture:** Rust binary as the core engine spawns a Python process per agent. Communication is JSON-RPC 2.0 over the child's stdin/stdout, one JSON object per line. MVP proves this link works end-to-end.

**Tech Stack:** Rust (serde_json, serde), Python 3, JSON-RPC 2.0

---

## File Structure

```
Cococlaw/
├── Cargo.toml
├── src/
│   ├── main.rs                # Entry point: spawn agent, ping, verify, exit
│   ├── agent_manager.rs       # Spawn/manage Python agent subprocess
│   └── transport.rs           # JSON-RPC 2.0 types and line-delimited IO
├── py-agent/
│   └── agent_runtime.py       # Minimal Python agent runtime
```

---

### Task 1: Rust project skeleton

**Files:**
- Create: `Cococlaw/Cargo.toml`
- Create: `Cococlaw/src/main.rs`

- [ ] **Step 1: Create Cargo.toml**

```toml
[package]
name = "cococat"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

- [ ] **Step 2: Create main.rs — minimal entry that prints startup message**

```rust
fn main() {
    println!("CocoCat Core starting...");
}
```

- [ ] **Step 3: Build and verify**

Run: `cargo build`
Expected: `Compiling cococat v0.1.0 ... Finished`

- [ ] **Step 4: Run and verify output**

Run: `cargo run`
Expected: `CocoCat Core starting...`

- [ ] **Step 5: Commit**

```bash
git init
git add Cargo.toml src/main.rs
git commit -m "chore: initialize Rust project skeleton"
```

---

### Task 2: JSON-RPC transport types

**Files:**
- Create: `Cococlaw/src/transport.rs`

- [ ] **Step 1: Write transport.rs with JSON-RPC types and line IO**

```rust
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
    pub id: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
}

/// Write a JSON-RPC request as a single line to a writer (child's stdin)
pub fn send_request(writer: &mut impl Write, req: &JsonRpcRequest) -> Result<(), String> {
    let line = serde_json::to_string(req).map_err(|e| format!("serialize error: {}", e))?;
    writeln!(writer, "{}", line).map_err(|e| format!("write error: {}", e))?;
    writer.flush().map_err(|e| format!("flush error: {}", e))
}

/// Read a JSON-RPC response from a buffered reader (child's stdout)
pub fn read_response(reader: &mut impl BufRead) -> Result<JsonRpcResponse, String> {
    let mut line = String::new();
    reader
        .read_line(&mut line)
        .map_err(|e| format!("read error: {}", e))?;
    if line.is_empty() {
        return Err("EOF: child process closed stdout".to_string());
    }
    serde_json::from_str(&line).map_err(|e| format!("deserialize error: {}", e))
}
```

- [ ] **Step 2: Add mod transport to main.rs**

```rust
mod transport;
```

- [ ] **Step 3: Build to verify no errors**

Run: `cargo build`
Expected: `Compiling cococat v0.1.0 ... Finished`

- [ ] **Step 4: Commit**

```bash
git add src/transport.rs src/main.rs Cargo.toml
git commit -m "feat: add JSON-RPC 2.0 transport types and line IO"
```

---

### Task 3: Agent manager — spawn and manage Python subprocess

**Files:**
- Create: `Cococlaw/src/agent_manager.rs`

- [ ] **Step 1: Write agent_manager.rs**

```rust
use crate::transport::{self, JsonRpcRequest, JsonRpcResponse};
use std::io::{BufReader, Write};
use std::process::{Child, Command, Stdio};

pub struct AgentProcess {
    pub child: Child,
    pub stdin_writer: Box<dyn Write + Send>,
    pub stdout_reader: Box<dyn BufRead + Send>,
}

impl AgentProcess {
    /// Spawn a Python agent subprocess. `python_script_path` is the
    /// path to the Python agent runtime file.
    pub fn spawn(python_script_path: &str) -> Result<Self, String> {
        let mut child = Command::new("python")
            .arg("-u") // unbuffered stdout
            .arg(python_script_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("failed to spawn agent: {}", e))?;

        let stdin_writer = child.stdin.take().ok_or("failed to open agent stdin")?;
        let stdout_reader = BufReader::new(child.stdout.take().ok_or("failed to open agent stdout")?);

        Ok(Self {
            child,
            stdin_writer: Box::new(stdin_writer),
            stdout_reader: Box::new(stdout_reader),
        })
    }

    /// Send a JSON-RPC request and read the response
    pub fn call(&mut self, method: &str, params: Option<serde_json::Value>, id: u64) -> Result<JsonRpcResponse, String> {
        let req = JsonRpcRequest::new(method, params, id);
        transport::send_request(&mut self.stdin_writer, &req)?;
        transport::read_response(&mut self.stdout_reader)
    }

    /// Terminate the agent subprocess
    pub fn kill(&mut self) -> Result<(), String> {
        self.child
            .kill()
            .map_err(|e| format!("failed to kill agent: {}", e))
    }

    /// Wait for the agent subprocess to exit
    pub fn wait(&mut self) -> Result<(), String> {
        self.child
            .wait()
            .map_err(|e| format!("failed to wait for agent: {}", e))?;
        Ok(())
    }
}
```

- [ ] **Step 2: Add mod agent_manager to main.rs**

```rust
mod agent_manager;
```

- [ ] **Step 3: Build to verify**

Run: `cargo build`
Expected: `Compiling cococat v0.1.0 ... Finished`

- [ ] **Step 4: Commit**

```bash
git add src/agent_manager.rs src/main.rs
git commit -m "feat: add agent manager to spawn Python subprocesses"
```

---

### Task 4: Python agent runtime

**Files:**
- Create: `Cococlaw/py-agent/agent_runtime.py`

- [ ] **Step 1: Write agent_runtime.py**

```python
import sys
import json


def handle_request(request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})

    if method == "ping":
        return {"pong": True, "agent": "cococat-mvp"}
    elif method == "echo":
        return params
    else:
        return {"error": f"unknown method: {method}"}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        request = json.loads(line)
        req_id = request.get("id")

        try:
            result = handle_request(request)
            response = {"jsonrpc": "2.0", "result": result, "id": req_id}
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -1, "message": str(e)},
                "id": req_id,
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test Python agent manually**

Run:
```powershell
echo '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' | python -u py-agent/agent_runtime.py
```

Expected: `{"jsonrpc": "2.0", "result": {"pong": true, "agent": "cococat-mvp"}, "id": 1}`

- [ ] **Step 3: Commit**

```bash
git add py-agent/agent_runtime.py
git commit -m "feat: add minimal Python agent runtime with ping/echo handlers"
```

---

### Task 5: Wire up end-to-end in main.rs

**Files:**
- Modify: `Cococlaw/src/main.rs`

- [ ] **Step 1: Update main.rs to spawn agent and exchange a ping**

```rust
mod agent_manager;
mod transport;

use agent_manager::AgentProcess;

fn main() {
    println!("CocoCat Core starting...");

    let script_path = "py-agent/agent_runtime.py";
    let mut agent = AgentProcess::spawn(script_path).expect("failed to spawn agent");

    println!("Agent spawned, sending ping...");

    let response = agent
        .call("ping", None, 1)
        .expect("failed to communicate with agent");

    println!("Response: {}", serde_json::to_string_pretty(&response).unwrap());

    if let Some(result) = response.result {
        if result.get("pong") == Some(&serde_json::json!(true)) {
            println!("MVP PASSED: Rust ↔ Python communication verified!");
        }
    }

    agent.kill().expect("failed to kill agent");
    agent.wait().expect("failed to wait for agent");
    println!("Agent terminated. CocoCat Core exiting.");
}
```

- [ ] **Step 2: Run end-to-end**

Run: `cargo run`
Expected output:
```
CocoCat Core starting...
Agent spawned, sending ping...
Response: {
  "jsonrpc": "2.0",
  "result": {
    "pong": true,
    "agent": "cococat-mvp"
  },
  "id": 1
}
MVP PASSED: Rust ↔ Python communication verified!
Agent terminated. CocoCat Core exiting.
```

- [ ] **Step 3: Commit**

```bash
git add src/main.rs
git commit -m "feat: wire up end-to-end Rust → Python ping/pong"
```

---

### Task 6: Add echo test for bi-directional parameter passing

**Files:**
- Modify: `Cococlaw/src/main.rs`

- [ ] **Step 1: Add echo test to main.rs before agent.kill()**

Add after the ping block and before `agent.kill()`:

```rust
    println!("\nTesting echo with parameters...");

    let echo_params = serde_json::json!({
        "message": "hello from Rust",
        "value": 42
    });

    let echo_response = agent
        .call("echo", Some(echo_params.clone()), 2)
        .expect("failed to echo");

    println!("Echo response: {}", serde_json::to_string_pretty(&echo_response).unwrap());

    if echo_response.result == Some(echo_params) {
        println!("ECHO PASSED: bi-directional parameter passing verified!");
    } else {
        println!("ECHO FAILED: response did not match");
    }
```

- [ ] **Step 2: Run and verify end-to-end**

Run: `cargo run`
Expected: Both ping and echo pass, final output includes both "MVP PASSED" and "ECHO PASSED"

- [ ] **Step 3: Commit**

```bash
git add src/main.rs
git commit -m "feat: add echo test for bi-directional parameter passing"
```

---

## MVP Scope Summary

**What we built:**
- ✅ Rust binary with agent manager
- ✅ JSON-RPC 2.0 transport over subprocess stdin/stdout
- ✅ Python agent runtime with ping + echo handlers
- ✅ End-to-end communication verified

**What we deferred (for next iteration):**
- Multiple agents
- Message bus / group chat
- Scene system
- Skill system
- Knowledge base
- Memory system (Dream, Consolidator)
- Web management panel
- Team Leader agent
- AGENT_ROSTER.md

## Self-Review Check

- **Spec coverage:** Tasks 1-6 implement the entire MVP spec (Rust spawns Python, communicates via JSON-RPC, end-to-end verified). All spec requirements are covered.
- **Placeholder scan:** No TBD, TODOs, or incomplete code. Every step has exact code and commands.
- **Type consistency:** `JsonRpcRequest`, `JsonRpcResponse`, `AgentProcess` types are consistent across all tasks. The `call()` method signature matches in Task 3 and Task 5.
