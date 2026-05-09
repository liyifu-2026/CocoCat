# Rust Tests Plan

**Goal:** Add unit tests for Rust core modules.

---

### Task 1: Add transport + message_bus tests

**Files:**
- Create: `tests/transport_test.rs`
- Create: `tests/message_bus_test.rs`

- [ ] **Step 1: Create transport tests**

`C:\Users\12991\Desktop\Cococlaw\tests\transport_test.rs`:

```rust
use cococat::transport::{JsonRpcRequest, JsonRpcResponse, JsonRpcError};

#[test]
fn test_request_creation() {
    let req = JsonRpcRequest::new("ping", None, 1);
    assert_eq!(req.method, "ping");
    assert_eq!(req.id, 1);
    assert_eq!(req.jsonrpc, "2.0");
}

#[test]
fn test_request_with_params() {
    let params = serde_json::json!({"key": "value"});
    let req = JsonRpcRequest::new("echo", Some(params.clone()), 2);
    assert_eq!(req.params, Some(params));
}

#[test]
fn test_response_with_result() {
    let resp = JsonRpcResponse {
        jsonrpc: "2.0".to_string(),
        result: Some(serde_json::json!({"pong": true})),
        error: None,
        id: Some(1),
    };
    assert!(resp.result.is_some());
    assert!(resp.error.is_none());
}

#[test]
fn test_response_with_error() {
    let resp = JsonRpcResponse {
        jsonrpc: "2.0".to_string(),
        result: None,
        error: Some(JsonRpcError { code: -32603, message: "test error".to_string() }),
        id: Some(1),
    };
    assert!(resp.result.is_none());
    assert!(resp.error.is_some());
    assert_eq!(resp.error.unwrap().code, -32603);
}
```

- [ ] **Step 2: Create message_bus tests**

`C:\Users\12991\Desktop\Cococlaw\tests\message_bus_test.rs`:

```rust
use cococat::message_bus::ChatMessage;

#[test]
fn test_chat_message_creation() {
    let msg = ChatMessage {
        timestamp: "2026-01-01T00:00:00Z".to_string(),
        from: "leader".to_string(),
        to: "*".to_string(),
        content: "Hello team".to_string(),
        message_type: "system".to_string(),
    };
    assert_eq!(msg.from, "leader");
    assert_eq!(msg.content, "Hello team");
}

#[test]
fn test_chat_message_serialization() {
    let msg = ChatMessage {
        timestamp: "2026-01-01T00:00:00Z".to_string(),
        from: "a".to_string(), to: "b".to_string(),
        content: "hi".to_string(), message_type: "text".to_string(),
    };
    let json = serde_json::to_string(&msg).unwrap();
    assert!(json.contains("\"from\":\"a\""));
    assert!(json.contains("\"content\":\"hi\""));
}

#[test]
fn test_chat_message_deserialization() {
    let json = r#"{"timestamp":"2026-01-01T00:00:00Z","from":"leader","to":"*","content":"hi","message_type":"text"}"#;
    let msg: ChatMessage = serde_json::from_str(json).unwrap();
    assert_eq!(msg.from, "leader");
}
```

- [ ] **Step 3: Make modules public for testing**

Read `C:\Users\12991\Desktop\Cococlaw\src\lib.rs`. If it doesn't exist, create it:

```rust
pub mod transport;
pub mod message_bus;
```

Also update `src/main.rs` to use `mod` instead of redefining modules:

Actually, the simplest way: add `pub use` in lib.rs. But the current structure uses modules in main.rs. Let me take a simpler approach: add a `lib.rs` that re-exports the modules.

```rust
// src/lib.rs
pub mod transport;
pub mod message_bus;
```

And in `src/main.rs`, change:
```rust
mod transport;
mod message_bus;
```
to:
```rust
// modules are declared in lib.rs
```

Actually, the simplest approach: create lib.rs and have main.rs use it.

`src/lib.rs`:
```rust
pub mod transport;
pub mod message_bus;
```

`src/main.rs`: Add `mod agent_manager; mod agent_registry;` (keep local modules), and use `use cococat::...` for the lib modules.

Actually the cleanest approach: just add `pub mod` declarations in main.rs and reference them in tests as `cococat::transport::...`. But for that I need a lib.rs.

Let me just create src/lib.rs with the modules the tests need, and keep main.rs as is. The lib.rs and main.rs can both declare the same modules in Rust.

Actually no, in Rust you can't have the same module declared in both lib.rs and main.rs. The proper approach is:
1. Create `src/lib.rs` with the modules
2. In `main.rs`, just add `use cococat::transport;` etc.

But this requires that main.rs doesn't also declare those modules. So I need to move the module declarations to lib.rs.

Let me take the simplest approach: create `src/lib.rs` that re-exports, and update `main.rs` to not declare those modules directly.

Actually the issue is that in Rust, when you have both lib.rs and main.rs in the same project, they're separate crates. Modules declared in main.rs are NOT accessible from lib.rs, and vice versa.

The standard approach is to put all the shared code in lib.rs, and have main.rs call into it.

Let me just put the testable modules (transport, message_bus) in lib.rs and reference them from there.

`src/lib.rs`:
```rust
pub mod transport;
pub mod message_bus;
```

`src/main.rs`: Remove `mod transport;` and `mod message_bus;` (they'll be in lib.rs), change references to use `cococat::transport::...` or just add `use cococat::transport;` etc.

But wait, that breaks existing code that uses `transport::send_request()` etc. Those would need to become `cococat::transport::send_request()` or I'd need to add `use cococat::transport;` at the top of main.rs.

For the tests to access modules, the modules must be public AND declared in lib.rs. Then tests use `cococat::module::Item`.

Let me set this up properly.

- [ ] **Step 3: Create src/lib.rs and update main.rs**

`src/lib.rs`:
```rust
pub mod transport;
pub mod message_bus;
```

In `src/main.rs`, remove the `mod transport;` and `mod message_bus;` lines. Add at the top:
```rust
use cococat::transport;
use cococat::message_bus;
```

- [ ] **Step 4: Run Rust tests**

```bash
cargo test
```

- [ ] **Step 5: Build to make sure everything still works**

```bash
cargo build
```

- [ ] **Step 6: Commit**

```bash
git add src/lib.rs src/main.rs tests/ Cargo.toml
git commit -m "test: add Rust tests for transport and message_bus modules"
```
