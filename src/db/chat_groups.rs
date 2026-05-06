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
        .query_row("SELECT COUNT(*) > 0 FROM chat_groups", [], |row| row.get(0))
        .unwrap_or(false);
    if exists {
        return Ok(());
    }
    conn.execute(
        "INSERT INTO chat_groups (id, name, announcement, is_default) VALUES (?1, ?2, ?3, 1)",
        params!["general", "General", "Default group chat for all team members."],
    )?;
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
    conn.execute(
        "INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, ?2, ?3, 'owner')",
        params!["general", "admin", "Admin"],
    )?;
    // Create DM groups for each agent
    let mut agents = conn.prepare("SELECT id, name FROM agents WHERE status != 'stopped'")?;
    let agent_rows: Vec<(String, String)> = agents
        .query_map([], |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)))?
        .filter_map(|r| r.ok())
        .collect();
    drop(agents);

    for (agent_id, agent_name) in &agent_rows {
        let dm_id = format!("dm_{}", agent_id);
        conn.execute(
            "INSERT OR IGNORE INTO chat_groups (id, name, announcement, is_default) VALUES (?1, ?2, '', 0)",
            rusqlite::params![dm_id, agent_name],
        )?;
        conn.execute(
            "INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, 'admin', 'Admin', 'owner')",
            rusqlite::params![dm_id],
        )?;
        conn.execute(
            "INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, ?2, ?3, 'member')",
            rusqlite::params![dm_id, agent_id, agent_name],
        )?;
    }
    Ok(())
}

pub fn list_groups(pool: &DbPool) -> Result<Vec<ChatGroup>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, announcement, is_default, created_at FROM chat_groups ORDER BY created_at",
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
    let mut result = Vec::new();
    for mut group in groups {
        let mut mstmt = conn.prepare(
            "SELECT agent_id, name, role FROM chat_group_members WHERE group_id = ?1",
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
        "SELECT id, name, announcement, is_default, created_at FROM chat_groups WHERE id = ?1",
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
    let mut mstmt =
        conn.prepare("SELECT agent_id, name, role FROM chat_group_members WHERE group_id = ?1")?;
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
    conn.execute(
        "INSERT OR IGNORE INTO chat_group_members (group_id, agent_id, name, role) VALUES (?1, ?2, ?3, 'owner')",
        params![id, "admin", "Admin"],
    )?;
    drop(conn);
    Ok(get_group(pool, id)?.unwrap())
}

pub fn delete_group(pool: &DbPool, group_id: &str) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let is_default: bool = conn
        .query_row("SELECT is_default FROM chat_groups WHERE id = ?1", params![group_id], |row| {
            row.get::<_, i32>(0)
        })
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
        conn.execute("UPDATE chat_groups SET name = ?1 WHERE id = ?2", params![name, group_id])?;
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

pub fn parse_mentions(content: &str) -> Vec<String> {
    let mut mentions = Vec::new();
    for word in content.split_whitespace() {
        if let Some(name) = word.strip_prefix('@') {
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
    let meta = serde_json::json!({"mentions": mentions, "read_by": []});
    let mentions_json = serde_json::to_string(&meta)?;
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO messages (msg_uuid, agent_id, user_id, role, content, scene_id, chat_group, metadata)
         VALUES (?1, NULL, ?2, 'user', ?3, 'default', ?4, ?5)",
        params![uuid::Uuid::new_v4().to_string(), from, content, group_id, mentions_json],
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
         ORDER BY created_at ASC LIMIT ?2",
    )?;
    let messages = stmt
        .query_map(params![group_id, limit], |row| {
            let metadata: String = row.get(4)?;
            let meta: serde_json::Value = serde_json::from_str(&metadata).unwrap_or_default();
            let mentions: Vec<String> = meta
                .get("mentions")
                .and_then(|v| serde_json::from_value(v.clone()).ok())
                .unwrap_or_default();
            let read_by: Vec<ReadReceipt> = meta
                .get("read_by")
                .and_then(|v| serde_json::from_value(v.clone()).ok())
                .unwrap_or_default();
            Ok(ChatMessage {
                id: row.get(0)?,
                from: row.get(1)?,
                content: row.get(2)?,
                timestamp: row.get(3)?,
                recalled: false,
                mentions,
                read_by,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();
    Ok(messages)
}

pub fn recall_message(pool: &DbPool, msg_id: i64) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute("UPDATE messages SET content = '[recalled]' WHERE id = ?1", params![msg_id])?;
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
        .query_row("SELECT metadata FROM messages WHERE id = ?1", params![msg_id], |row| row.get(0))
        .unwrap_or_default();
    let mut meta: serde_json::Value =
        serde_json::from_str(&existing).unwrap_or(serde_json::Value::Object(Default::default()));
    let read_by = meta
        .get_mut("read_by")
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
        params![uuid::Uuid::new_v4().to_string(), agent_id, agent_id, content, scene_id, chat_group],
    )?;
    Ok(conn.last_insert_rowid())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::pool::create_test_pool;

    fn insert_test_agent(pool: &DbPool, id: &str, name: &str) {
        let conn = pool.get().unwrap();
        conn.execute(
            "INSERT OR IGNORE INTO agents (id, name, role, model, status, scene_id) VALUES (?1, ?2, 'test', 'test', 'running', 'default')",
            params![id, name],
        ).unwrap();
    }

    #[test]
    fn test_init_default_group_empty() {
        let pool = create_test_pool();
        insert_test_agent(&pool, "admin", "Admin");
        init_default_group(&pool).unwrap();
        let groups = list_groups(&pool).unwrap();
        assert_eq!(groups.len(), 1);
        assert_eq!(groups[0].id, "general");
        assert!(groups[0].is_default);
    }

    #[test]
    fn test_create_and_get_group() {
        let pool = create_test_pool();
        insert_test_agent(&pool, "admin", "Admin");
        insert_test_agent(&pool, "test_a", "TestA");
        let members = vec![ChatGroupMember { agent_id: "test_a".into(), name: "TestA".into(), role: "member".into() }];
        let group = create_group(&pool, "test-group", "Test Group", "Hello", &members).unwrap();
        assert_eq!(group.id, "test-group");
        assert_eq!(group.name, "Test Group");
        assert!(!group.is_default);
        let fetched = get_group(&pool, "test-group").unwrap().unwrap();
        assert_eq!(fetched.name, "Test Group");
        assert_eq!(fetched.members.len(), 2);
    }

    #[test]
    fn test_send_and_get_messages() {
        let pool = create_test_pool();
        insert_test_agent(&pool, "admin", "Admin");
        insert_test_agent(&pool, "test_a", "TestA");
        let members = vec![ChatGroupMember { agent_id: "test_a".into(), name: "TestA".into(), role: "member".into() }];
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
