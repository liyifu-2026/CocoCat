# Chat Groups Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate chat group storage from FastAPI JSONL files to Rust SQLite, enabling agent responses in the Chat page.

**Architecture:** Add 2 new SQLite tables (`chat_groups`, `chat_group_members`), a new Rust DB module + API module, then modify the dispatch engine to write agent replies back to the messages table. FastAPI chat_groups.py becomes a proxy to Rust.

**Tech Stack:** Rust (rusqlite, axum), FastAPI (httpx), SQLite

---

### Task 1: Add database tables to migration

**Files:**
- Modify: `src/db/pool.rs:110-127` — add CREATE TABLE statements

- [ ] **Step 1: Add chat_groups and chat_group_members tables**

Insert after the `skills` table creation in `run_migrations()`:

```rust
        CREATE TABLE IF NOT EXISTS chat_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            announcement TEXT NOT NULL DEFAULT '',
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_group_members (
            group_id TEXT NOT NULL REFERENCES chat_groups(id),
            agent_id TEXT NOT NULL REFERENCES agents(id),
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            PRIMARY KEY (group_id, agent_id)
        );
```

- [ ] **Step 2: Verify compilation**

Run: `cargo check`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/db/pool.rs
git commit -m "feat: add chat_groups and chat_group_members tables"
```

---

### Task 2: Create chat_groups DB module

**Files:**
- Create: `src/db/chat_groups.rs` — all DB operations for groups and messages
- Modify: `src/db/mod.rs` — declare the module

- [ ] **Step 1: Add module declaration to mod.rs**

Read the existing `src/db/mod.rs` first, then add:
```rust
pub mod chat_groups;
```

- [ ] **Step 2: Create `src/db/chat_groups.rs` with all DB operations**

```rust
use crate::db::models::Message;
use crate::db::pool::DbPool;
use rusqlite::params;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatGroup {
    pub id: String,
    pub name: String,
    pub announcement: String,
    pub is_default: bool,
    pub created_at: String,
    pub members: Vec<ChatGroupMember>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatGroupMember {
    pub agent_id: String,
    pub name: String,
    pub role: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub id: i64,
    pub from: String,
    pub content: String,
    pub timestamp: String,
    pub recalled: bool,
    pub mentions: Vec<String>,
    pub read_by: Vec<ReadReceipt>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReadReceipt {
    pub agent_id: String,
    pub read_at: String,
    pub score: i64,
}

pub fn init_default_group(pool: &DbPool) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let exists: bool = conn
        .query_row(
            "SELECT COUNT(*) > 0 FROM chat_groups",
            [],
            |row| row.get(0),
        )
        .unwrap_or(false);
    if exists {
        return Ok(());
    }

    conn.execute(
        "INSERT INTO chat_groups (id, name, announcement, is_default) VALUES (?1, ?2, ?3, 1)",
        params!["general", "General", "Default group chat for all team members."],
    )?;

    // Populate members from agents table
    let mut stmt = conn.prepare("SELECT id, name FROM agents WHERE status != 'stopped'")?;
    let members: Vec<(String, String)> = stmt
        .query_map([], |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)))?
        .filter_map(|r| r.ok())
        .collect();
    drop(stmt);

    for (agent_id, name) in &members {
        conn.execute(
            "INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, ?2, ?3, 'member')",
            params!["general", agent_id, name],
        )?;
    }

    // Add admin member
    conn.execute(
        "INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, ?2, ?3, 'owner')",
        params!["general", "admin", "Admin"],
    )?;

    Ok(())
}

pub fn list_groups(pool: &DbPool) -> Result<Vec<ChatGroup>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, announcement, is_default, created_at FROM chat_groups ORDER BY created_at"
    )?;

    let groups: Vec<ChatGroup> = stmt
        .query_map([], |row| {
            Ok(ChatGroup {
                id: row.get(0)?,
                name: row.get(1)?,
                announcement: row.get(2)?,
                is_default: row.get::<_, i32>(3)? != 0,
                created_at: row.get(4)?,
                members: Vec::new(),
            })
        })?
        .filter_map(|r| r.ok())
        .collect();
    drop(stmt);

    // Load members for each group
    let mut result = Vec::new();
    for mut group in groups {
        let mut mstmt = conn.prepare(
            "SELECT agent_id, name, role FROM chat_group_members WHERE group_id = ?1"
        )?;
        let members: Vec<ChatGroupMember> = mstmt
            .query_map(params![group.id], |row| {
                Ok(ChatGroupMember {
                    agent_id: row.get(0)?,
                    name: row.get(1)?,
                    role: row.get(2)?,
                })
            })?
            .filter_map(|r| r.ok())
            .collect();
        group.members = members;
        result.push(group);
    }

    Ok(result)
}

pub fn get_group(pool: &DbPool, group_id: &str) -> Result<Option<ChatGroup>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, announcement, is_default, created_at FROM chat_groups WHERE id = ?1"
    )?;

    let mut group = match stmt.query_row(params![group_id], |row| {
        Ok(ChatGroup {
            id: row.get(0)?,
            name: row.get(1)?,
            announcement: row.get(2)?,
            is_default: row.get::<_, i32>(3)? != 0,
            created_at: row.get(4)?,
            members: Vec::new(),
        })
    }) {
        Ok(g) => g,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
        Err(e) => return Err(e.into()),
    };
    drop(stmt);

    let mut mstmt = conn.prepare(
        "SELECT agent_id, name, role FROM chat_group_members WHERE group_id = ?1"
    )?;
    let members: Vec<ChatGroupMember> = mstmt
        .query_map(params![group_id], |row| {
            Ok(ChatGroupMember {
                agent_id: row.get(0)?,
                name: row.get(1)?,
                role: row.get(2)?,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();
    group.members = members;

    Ok(Some(group))
}

pub fn create_group(
    pool: &DbPool,
    id: &str,
    name: &str,
    announcement: &str,
    members: &[ChatGroupMember],
) -> Result<ChatGroup, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO chat_groups (id, name, announcement, is_default) VALUES (?1, ?2, ?3, 0)",
        params![id, name, announcement],
    )?;

    for m in members {
        conn.execute(
            "INSERT INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, ?2, ?3, ?4)",
            params![id, m.agent_id, m.name, m.role],
        )?;
    }

    // Add admin as owner
    conn.execute(
        "INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, ?2, ?3, 'owner')",
        params![id, "admin", "Admin"],
    )?;

    drop(conn);
    Ok(get_group(pool, id)?.unwrap())
}

pub fn delete_group(pool: &DbPool, group_id: &str) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    // Check if default
    let is_default: bool = conn
        .query_row(
            "SELECT is_default FROM chat_groups WHERE id = ?1",
            params![group_id],
            |row| row.get::<_, i32>(0),
        )
        .map(|v| v != 0)
        .unwrap_or(false);
    if is_default {
        return Err("cannot delete default group".into());
    }
    conn.execute("DELETE FROM chat_group_members WHERE group_id = ?1", params![group_id])?;
    conn.execute("DELETE FROM chat_groups WHERE id = ?1", params![group_id])?;
    Ok(())
}

pub fn update_group(
    pool: &DbPool,
    group_id: &str,
    name: Option<&str>,
    announcement: Option<&str>,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    if let Some(name) = name {
        conn.execute(
            "UPDATE chat_groups SET name = ?1 WHERE id = ?2",
            params![name, group_id],
        )?;
    }
    if let Some(announcement) = announcement {
        conn.execute(
            "UPDATE chat_groups SET announcement = ?1 WHERE id = ?2",
            params![announcement, group_id],
        )?;
    }
    Ok(())
}

pub fn add_member(
    pool: &DbPool,
    group_id: &str,
    agent_id: &str,
    name: &str,
    role: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, ?2, ?3, ?4)",
        params![group_id, agent_id, name, role],
    )?;
    Ok(())
}

pub fn remove_member(pool: &DbPool, group_id: &str, agent_id: &str) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "DELETE FROM chat_group_members WHERE group_id = ?1 AND agent_id = ?2",
        params![group_id, agent_id],
    )?;
    Ok(())
}

fn parse_mentions(content: &str) -> Vec<String> {
    let mut mentions = Vec::new();
    for word in content.split_whitespace() {
        if let Some(name) = word.strip_prefix('@') {
            // Strip trailing punctuation
            let name = name.trim_end_matches(&[',', '.', '!', '?', ';', ':', '\'', '"', '，', '。', '！', '？'][..]);
            if !name.is_empty() && name != "all" && name != "全体成员" && name != "所有人" {
                mentions.push(name.to_string());
            }
        }
    }
    mentions
}

pub fn send_message(
    pool: &DbPool,
    group_id: &str,
    content: &str,
    from: &str,
) -> Result<i64, Box<dyn std::error::Error>> {
    let mentions = parse_mentions(content);
    let mentions_json = serde_json::to_string(&mentions)?;
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, chat_group, metadata)
         VALUES (?1, ?2, ?3, 'user', ?4, 'default', ?5, ?6)",
        params![
            uuid::Uuid::new_v4().to_string(),
            from,
            from,
            content,
            group_id,
            mentions_json,
        ],
    )?;
    Ok(conn.last_insert_rowid())
}

pub fn get_messages(
    pool: &DbPool,
    group_id: &str,
    limit: i64,
) -> Result<Vec<ChatMessage>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, COALESCE(agent_id, user_id, ''), content, created_at, metadata
         FROM messages WHERE chat_group = ?1
         ORDER BY created_at ASC LIMIT ?2"
    )?;

    let messages = stmt
        .query_map(params![group_id, limit], |row| {
            let metadata: String = row.get(4)?;
            let mentions: Vec<String> = serde_json::from_str(&metadata).unwrap_or_default();
            Ok(ChatMessage {
                id: row.get(0)?,
                from: row.get(1)?,
                content: row.get(2)?,
                timestamp: row.get(3)?,
                recalled: false,
                mentions,
                read_by: Vec::new(),
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

    Ok(messages)
}

pub fn recall_message(
    pool: &DbPool,
    msg_id: i64,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE messages SET content = '[recalled]' WHERE id = ?1",
        params![msg_id],
    )?;
    Ok(())
}

pub fn mark_read(
    pool: &DbPool,
    msg_id: i64,
    agent_id: &str,
    score: i64,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let existing: String = conn
        .query_row(
            "SELECT metadata FROM messages WHERE id = ?1",
            params![msg_id],
            |row| row.get(0),
        )
        .unwrap_or_default();

    let mut meta: serde_json::Value = serde_json::from_str(&existing).unwrap_or(serde_json::Value::Object(Default::default()));
    let read_by = meta.get_mut("read_by")
        .and_then(|v| v.as_array_mut())
        .map(|arr| {
            if !arr.iter().any(|r| r.get("agent_id").and_then(|s| s.as_str()) == Some(agent_id)) {
                arr.push(serde_json::json!({
                    "agent_id": agent_id,
                    "read_at": chrono::Utc::now().to_rfc3339(),
                    "score": score,
                }));
            }
            arr.clone()
        })
        .unwrap_or_else(|| {
            vec![serde_json::json!({
                "agent_id": agent_id,
                "read_at": chrono::Utc::now().to_rfc3339(),
                "score": score,
            })]
        });

    if let serde_json::Value::Object(ref mut map) = meta {
        map.insert("read_by".to_string(), serde_json::Value::Array(read_by.clone()));
    }

    conn.execute(
        "UPDATE messages SET metadata = ?1 WHERE id = ?2",
        params![serde_json::to_string(&meta)?, msg_id],
    )?;
    Ok(())
}

pub fn insert_agent_reply(
    pool: &DbPool,
    chat_group: &str,
    agent_id: &str,
    content: &str,
    scene_id: &str,
) -> Result<i64, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, chat_group, metadata)
         VALUES (?1, ?2, ?3, 'assistant', ?4, ?5, ?6, '{}')",
        params![
            uuid::Uuid::new_v4().to_string(),
            agent_id,
            agent_id,
            content,
            scene_id,
            chat_group,
        ],
    )?;
    Ok(conn.last_insert_rowid())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::pool::create_test_pool;

    #[test]
    fn test_init_default_group_empty() {
        let pool = create_test_pool();
        init_default_group(&pool).unwrap();
        let groups = list_groups(&pool).unwrap();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0].id, "general");
        assert!(groups[0].is_default);
    }

    #[test]
    fn test_create_and_get_group() {
        let pool = create_test_pool();
        let members = vec![
            ChatGroupMember { agent_id: "test_a".into(), name: "TestA".into(), role: "member".into() },
        ];
        let group = create_group(&pool, "test-group", "Test Group", "Hello", &members).unwrap();
        assert_eq!(group.id, "test-group");
        assert_eq!(group.name, "Test Group");
        assert!(!group.is_default);

        let fetched = get_group(&pool, "test-group").unwrap().unwrap();
        assert_eq!(fetched.name, "Test Group");
        assert_eq!(fetched.members.len(), 2); // test_a + admin
    }

    #[test]
    fn test_send_and_get_messages() {
        let pool = create_test_pool();
        let members = vec![
            ChatGroupMember { agent_id: "test_a".into(), name: "TestA".into(), role: "member".into() },
        ];
        create_group(&pool, "g1", "G1", "", &members).unwrap();

        let msg_id = send_message(&pool, "g1", "Hello @test_a", "admin").unwrap();
        assert!(msg_id > 0);

        let msgs = get_messages(&pool, "g1", 10).unwrap();
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].content, "Hello @test_a");
        assert_eq!(msgs[0].mentions, vec!["test_a"]);
    }

    #[test]
    fn test_parse_mentions() {
        let result = parse_mentions("Hello @test_a and @test_b!");
        assert_eq!(result, vec!["test_a", "test_b"]);
    }
}
```

- [ ] **Step 3: Verify compilation**

Run: `cargo check`
Expected: No errors

- [ ] **Step 4: Run tests**

Run: `cargo test --lib db::chat_groups`
Expected: All 4 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/db/mod.rs src/db/chat_groups.rs
git commit -m "feat: add chat_groups DB module with group CRUD and messaging"
```

---

### Task 3: Create chat_groups API module

**Files:**
- Create: `src/api/chat_groups.rs` — REST handlers
- Modify: `src/api/mod.rs` — declare module

- [ ] **Step 1: Register module**

Add to `src/api/mod.rs`:
```rust
pub mod chat_groups;
```

- [ ] **Step 2: Create `src/api/chat_groups.rs`**

```rust
use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use serde::{Deserialize, Serialize};

use crate::auth;
use crate::db::chat_groups::{self as db_chat, ChatGroup, ChatGroupMember, ChatMessage};
use crate::db::tasks;
use crate::db::models::NewTask;
use crate::dispatch::engine::TaskEvent;

use super::router::AppState;

#[derive(Deserialize)]
pub struct CreateGroupRequest {
    pub name: String,
    pub members: Vec<MemberEntry>,
    pub announcement: Option<String>,
}

#[derive(Deserialize)]
pub struct MemberEntry {
    pub id: String,
    pub name: String,
    pub role: Option<String>,
}

#[derive(Deserialize)]
pub struct SendMessageRequest {
    pub content: String,
    pub from: Option<String>,
}

#[derive(Serialize)]
pub struct SendMessageResponse {
    pub status: String,
    pub message: ChatMessage,
}

#[derive(Deserialize)]
pub struct UpdateGroupRequest {
    pub name: Option<String>,
    pub announcement: Option<String>,
}

#[derive(Deserialize)]
pub struct AddMemberRequest {
    pub agent_id: String,
    pub name: String,
}

#[derive(Deserialize)]
pub struct MarkReadRequest {
    pub agent_id: String,
    pub score: Option<i64>,
}

#[derive(Deserialize)]
pub struct MessagesQuery {
    pub limit: Option<i64>,
}

// GET /api/chat/groups
pub async fn list_groups(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let groups = db_chat::list_groups(&state.db_pool).map_err(|e| {
        tracing::error!("list_groups: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({"groups": groups})))
}

// POST /api/chat/groups
pub async fn create_group(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<CreateGroupRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let group_id = req.name.to_lowercase().replace(' ', "-");
    let members: Vec<ChatGroupMember> = req.members.into_iter().map(|m| ChatGroupMember {
        agent_id: m.id,
        name: m.name,
        role: m.role.unwrap_or_else(|| "member".to_string()),
    }).collect();

    let group = db_chat::create_group(
        &state.db_pool,
        &group_id,
        &req.name,
        req.announcement.as_deref().unwrap_or(""),
        &members,
    ).map_err(|e| {
        tracing::error!("create_group: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(serde_json::json!({"status": "created", "group": group})))
}

// GET /api/chat/groups/{group_id}
pub async fn get_group(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    match db_chat::get_group(&state.db_pool, &group_id).map_err(|e| {
        tracing::error!("get_group: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })? {
        Some(group) => Ok(Json(serde_json::json!(group))),
        None => Ok(Json(serde_json::json!({"error": "group not found"}))),
    }
}

// PATCH /api/chat/groups/{group_id}
pub async fn update_group(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
    Json(req): Json<UpdateGroupRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::update_group(&state.db_pool, &group_id, req.name.as_deref(), req.announcement.as_deref())
        .map_err(|e| {
            tracing::error!("update_group: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "updated"})))
}

// DELETE /api/chat/groups/{group_id}
pub async fn delete_group(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::delete_group(&state.db_pool, &group_id).map_err(|e| {
        tracing::error!("delete_group: {}", e);
        StatusCode::BAD_REQUEST
    })?;
    Ok(Json(serde_json::json!({"status": "deleted"})))
}

// POST /api/chat/groups/{group_id}/members
pub async fn add_member(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
    Json(req): Json<AddMemberRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::add_member(&state.db_pool, &group_id, &req.agent_id, &req.name, "member")
        .map_err(|e| {
            tracing::error!("add_member: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "added"})))
}

// DELETE /api/chat/groups/{group_id}/members/{agent_id}
pub async fn remove_member(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((group_id, agent_id)): Path<(String, String)>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    if agent_id == "admin" {
        return Ok(Json(serde_json::json!({"error": "cannot remove admin"})));
    }
    db_chat::remove_member(&state.db_pool, &group_id, &agent_id)
        .map_err(|e| {
            tracing::error!("remove_member: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "removed"})))
}

// POST /api/chat/groups/{group_id}/messages
pub async fn send_message(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
    Json(req): Json<SendMessageRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let content = req.content.trim().to_string();
    if content.is_empty() {
        return Ok(Json(serde_json::json!({"error": "content is required"})));
    }
    let from = req.from.unwrap_or_else(|| "admin".to_string());

    // Get group to find members
    let group = db_chat::get_group(&state.db_pool, &group_id)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    // Insert user message
    let msg_id = db_chat::send_message(&state.db_pool, &group_id, &content, &from)
        .map_err(|e| {
            tracing::error!("send_message: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Determine which agents to dispatch to
    let mentions = db_chat::parse_mentions(&content);
    let target_agents: Vec<String> = if mentions.is_empty() {
        // No mentions: dispatch to first non-admin member
        group.members.iter()
            .filter(|m| m.agent_id != "admin")
            .map(|m| m.agent_id.clone())
            .take(1)
            .collect()
    } else {
        mentions
    };

    // Create task for each target agent
    for agent_id in &target_agents {
        let task_uuid = uuid::Uuid::new_v4().to_string();
        let params = serde_json::json!({
            "content": content,
            "chat_group": group_id,
            "source_msg_id": msg_id,
            "scene_id": "default",
        });

        if let Err(e) = tasks::create_task(
            &state.db_pool,
            &NewTask {
                task_uuid: task_uuid.clone(),
                target_agent: agent_id.clone(),
                source: "chat".into(),
                method: "chat".into(),
                params: params.to_string(),
            },
        ) {
            tracing::error!("create_task for {}: {}", agent_id, e);
            continue;
        }

        let _ = state.task_tx.send(TaskEvent::NewTask {
            task_uuid: task_uuid.clone(),
        }).await;
    }

    // Return the newly created message
    let messages = db_chat::get_messages(&state.db_pool, &group_id, 1).unwrap_or_default();
    let message = messages.last().cloned().unwrap_or(ChatMessage {
        id: msg_id,
        from: from.clone(),
        content: content.clone(),
        timestamp: chrono::Utc::now().to_rfc3339(),
        recalled: false,
        mentions: Default::default(),
        read_by: Default::default(),
    });

    Ok(Json(serde_json::json!({"status": "sent", "message": message})))
}

// GET /api/chat/groups/{group_id}/messages
pub async fn get_messages(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
    Query(query): Query<MessagesQuery>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let limit = query.limit.unwrap_or(100);
    let messages = db_chat::get_messages(&state.db_pool, &group_id, limit)
        .map_err(|e| {
            tracing::error!("get_messages: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"messages": messages})))
}

// POST /api/chat/groups/{group_id}/messages/{msg_id}/recall
pub async fn recall_message(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((_group_id, msg_id)): Path<(String, i64)>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::recall_message(&state.db_pool, msg_id)
        .map_err(|e| {
            tracing::error!("recall_message: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "recalled"})))
}

// POST /api/chat/groups/{group_id}/messages/{msg_id}/read
pub async fn mark_read(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((_group_id, msg_id)): Path<(String, i64)>,
    Json(req): Json<MarkReadRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::mark_read(&state.db_pool, msg_id, &req.agent_id, req.score.unwrap_or(0))
        .map_err(|e| {
            tracing::error!("mark_read: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "read"})))
}
```

- [ ] **Step 3: Verify compilation**

Run: `cargo check`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add src/api/mod.rs src/api/chat_groups.rs
git commit -m "feat: add chat_groups API handlers with agent dispatch"
```

---

### Task 4: Register routes and startup initialization

**Files:**
- Modify: `src/api/router.rs` — add chat group routes
- Modify: `src/main.rs` — call init_default_group on startup

- [ ] **Step 1: Add routes to router.rs**

Add after the existing routes (before `.layer(...)`):
```rust
        .route("/api/chat/groups", axum::routing::get(chat_groups::list_groups).post(chat_groups::create_group))
        .route("/api/chat/groups/{group_id}", axum::routing::get(chat_groups::get_group).patch(chat_groups::update_group).delete(chat_groups::delete_group))
        .route("/api/chat/groups/{group_id}/members", axum::routing::post(chat_groups::add_member))
        .route("/api/chat/groups/{group_id}/members/{agent_id}", axum::routing::delete(chat_groups::remove_member))
        .route("/api/chat/groups/{group_id}/messages", axum::routing::post(chat_groups::send_message).get(chat_groups::get_messages))
        .route("/api/chat/groups/{group_id}/messages/{msg_id}/recall", axum::routing::post(chat_groups::recall_message))
        .route("/api/chat/groups/{group_id}/messages/{msg_id}/read", axum::routing::post(chat_groups::mark_read))
```

And add the `use` at the top:
```rust
use super::chat_groups;
```

- [ ] **Step 2: Add startup initialization to main.rs**

After `db::pool::run_migrations(&db_pool)?;`, add:
```rust
    db::chat_groups::init_default_group(&db_pool)?;
```

And add the chat_groups module import at the top of main.rs (inside the `mod` block):
```rust
mod chat_groups;  // alongside other mod declarations
```

Wait — the modules are declared in `lib.rs` or `main.rs`? Let me check. Looking at `src/main.rs`:
```rust
mod agent;
mod api;
mod auth;
mod config;
mod db;
mod dispatch;
```

So modules are declared in main.rs directly. But the DB module `chat_groups` is declared inside `src/db/mod.rs`. So I don't need to add anything to main.rs for the module — only for calling `init_default_group`.

- [ ] **Step 3: Add init call to main.rs**

```rust
    db::chat_groups::init_default_group(&db_pool)?;
```

- [ ] **Step 4: Verify compilation**

Run: `cargo check`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add src/api/router.rs src/main.rs
git commit -m "feat: register chat_groups routes and init default group on startup"
```

---

### Task 5: Modify dispatch engine to write agent replies to chat

**Files:**
- Modify: `src/dispatch/engine.rs` — after task completion, insert agent reply to messages table

- [ ] **Step 1: Modify process_task to capture chat origin before closure**

In `src/dispatch/engine.rs`, before the `spawn_blocking` call, extract chat metadata from params:

```rust
    // Capture chat origin info before params/target are moved into closure
    let chat_group = params.get("chat_group").and_then(|v| v.as_str()).map(|s| s.to_string());
    let scene_id = params.get("scene_id").and_then(|v| v.as_str()).map(|s| s.to_string());
```

Then, inside the `Ok(result)` match arm, after `tasks::complete_task()`, add:

```rust
            // If task originated from chat, insert agent reply into messages table
            if let (Some(ref cg), Some(ref sid)) = (chat_group, scene_id) {
                let reply = result.get("response")
                    .and_then(|v| v.as_str())
                    .or_else(|| result.get("content").and_then(|v| v.as_str()))
                    .unwrap_or("");
                if !reply.is_empty() {
                    let _ = crate::db::chat_groups::insert_agent_reply(
                        db_pool, cg, &target, reply, sid,
                    );
                }
            }
```

- [ ] **Step 2: Verify compilation**

Run: `cargo check`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/dispatch/engine.rs
git commit -m "feat: write agent replies to chat messages table on task completion"
```

---

### Task 6: FastAPI proxy — replace JSONL with Rust API calls

**Files:**
- Modify: `web/routes/chat_groups.py` — replace all file-based operations with httpx proxy to Rust

- [ ] **Step 1: Rewrite chat_groups.py as a proxy**

```python
"""Chat group routes — proxies to Rust HTTP API (replaces old JSONL storage)."""
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()
RUST_API = "http://localhost:3000/api/chat/groups"


async def _proxy(method: str, path: str, body: dict | None = None, params: dict | None = None):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{RUST_API}{path}"
            resp = await client.request(method, url, json=body, params=params, timeout=30)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)


@router.get("/api/chat/groups")
async def list_groups():
    return await _proxy("GET", "")


@router.post("/api/chat/groups")
async def create_group(body: dict):
    return await _proxy("POST", "", body)


@router.get("/api/chat/groups/{group_id}")
async def get_group(group_id: str):
    return await _proxy("GET", f"/{group_id}")


@router.patch("/api/chat/groups/{group_id}")
async def update_group(group_id: str, body: dict):
    return await _proxy("PATCH", f"/{group_id}", body)


@router.delete("/api/chat/groups/{group_id}")
async def delete_group_route(group_id: str):
    return await _proxy("DELETE", f"/{group_id}")


@router.post("/api/chat/groups/{group_id}/members")
async def add_member(group_id: str, body: dict):
    return await _proxy("POST", f"/{group_id}/members", body)


@router.delete("/api/chat/groups/{group_id}/members/{agent_id}")
async def remove_member(group_id: str, agent_id: str):
    return await _proxy("DELETE", f"/{group_id}/members/{agent_id}")


@router.post("/api/chat/groups/{group_id}/messages")
async def send_message(group_id: str, body: dict):
    return await _proxy("POST", f"/{group_id}/messages", body)


@router.get("/api/chat/groups/{group_id}/messages")
async def get_messages(group_id: str, limit: int = 100):
    return await _proxy("GET", f"/{group_id}/messages", params={"limit": limit})


@router.post("/api/chat/groups/{group_id}/messages/{msg_id}/recall")
async def recall_message(group_id: str, msg_id: int):
    return await _proxy("POST", f"/{group_id}/messages/{msg_id}/recall")


@router.post("/api/chat/groups/{group_id}/messages/{msg_id}/read")
async def mark_read(group_id: str, msg_id: int, body: dict):
    return await _proxy("POST", f"/{group_id}/messages/{msg_id}/read", body)
```

- [ ] **Step 2: Verify FastAPI import**

Run: `python3 -c "import web.main; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add web/routes/chat_groups.py
git commit -m "feat: proxy chat_groups routes to Rust core, remove JSONL storage"
```

---

### Task 7: Full integration test

- [ ] **Step 1: Build Rust**

```bash
cargo build --bin cococat
```

- [ ] **Step 2: Start Rust core**

```bash
cargo run --bin cococat &
sleep 3
```

- [ ] **Step 3: Start FastAPI**

```bash
uvicorn web.main:app --host 0.0.0.0 --port 8000 &
sleep 2
```

- [ ] **Step 4: Test group listing**

```bash
curl -s http://localhost:3000/api/chat/groups | python3 -m json.tool
```
Expected: Shows "General" group with members.

- [ ] **Step 5: Test sending a message through the proxy**

```bash
# Login first
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"password":"123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

# Send message mentioning a leader agent
curl -s -X POST http://localhost:8000/api/chat/groups/general/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Hello @leader, test message from admin"}' | python3 -m json.tool
```

- [ ] **Step 6: Read messages back**

```bash
curl -s http://localhost:8000/api/chat/groups/general/messages \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
Expected: Shows user message. After ~5-10 seconds, should also show agent reply.

- [ ] **Step 7: Clean up**

```bash
kill %1 %2 2>/dev/null; true
```

- [ ] **Step 8: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "chore: fix review issues"
```
