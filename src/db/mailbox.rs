use serde::{Deserialize, Serialize};

use crate::db::pool::DbPool;
use rusqlite::params;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MailMessage {
    pub id: i64,
    pub msg_uuid: String,
    pub from_agent: String,
    pub to_agent: String,
    pub subject: String,
    pub body: String,
    pub read: i32,
    pub created_at: String,
}

pub struct NewMailMessage {
    pub msg_uuid: String,
    pub from_agent: String,
    pub to_agent: String,
    pub subject: String,
    pub body: String,
}

pub fn send_message(
    pool: &DbPool,
    msg: &NewMailMessage,
) -> Result<MailMessage, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO mailbox (msg_uuid, from_agent, to_agent, subject, body)
         VALUES (?1, ?2, ?3, ?4, ?5)",
        params![msg.msg_uuid, msg.from_agent, msg.to_agent, msg.subject, msg.body],
    )?;
    let id = conn.last_insert_rowid();
    get_message(pool, id)
}

pub fn get_message(pool: &DbPool, id: i64) -> Result<MailMessage, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    Ok(conn.query_row(
        "SELECT id, msg_uuid, from_agent, to_agent, subject, body, read, created_at
         FROM mailbox WHERE id = ?1",
        params![id],
        |row| {
            Ok(MailMessage {
                id: row.get(0)?,
                msg_uuid: row.get(1)?,
                from_agent: row.get(2)?,
                to_agent: row.get(3)?,
                subject: row.get(4)?,
                body: row.get(5)?,
                read: row.get(6)?,
                created_at: row.get(7)?,
            })
        },
    )?)
}

pub fn get_inbox(
    pool: &DbPool,
    agent_id: &str,
    limit: i64,
) -> Result<Vec<MailMessage>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, msg_uuid, from_agent, to_agent, subject, body, read, created_at
         FROM mailbox WHERE to_agent = ?1
         ORDER BY created_at DESC LIMIT ?2"
    )?;
    let msgs = stmt.query_map(params![agent_id, limit], |row| {
        Ok(MailMessage {
            id: row.get(0)?,
            msg_uuid: row.get(1)?,
            from_agent: row.get(2)?,
            to_agent: row.get(3)?,
            subject: row.get(4)?,
            body: row.get(5)?,
            read: row.get(6)?,
            created_at: row.get(7)?,
        })
    })?
    .filter_map(|r| r.ok())
    .collect();
    Ok(msgs)
}

pub fn mark_read(pool: &DbPool, id: i64) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute("UPDATE mailbox SET read = 1 WHERE id = ?1", params![id])?;
    Ok(())
}

pub fn mark_all_read(pool: &DbPool, to_agent: &str) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute("UPDATE mailbox SET read = 1 WHERE to_agent = ?1", params![to_agent])?;
    Ok(())
}

pub fn list_inboxes(pool: &DbPool) -> Result<Vec<serde_json::Value>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let agents = crate::db::agents::load_agents(pool)?;
    let mut result = vec![];
    for agent in &agents {
        let unread: i64 = conn.query_row(
            "SELECT COUNT(*) FROM mailbox WHERE to_agent = ?1 AND read = 0",
            params![agent.id],
            |row| row.get(0),
        ).unwrap_or(0);
        let latest = conn.query_row(
            "SELECT from_agent, body, created_at, CASE WHEN read = 1 THEN 'read' ELSE 'unread' END as status
             FROM mailbox WHERE to_agent = ?1 ORDER BY created_at DESC LIMIT 1",
            params![agent.id],
            |row| {
                Ok(serde_json::json!({
                    "from": row.get::<_, String>(0)?,
                    "content": row.get::<_, String>(1)?,
                    "timestamp": row.get::<_, String>(2)?,
                    "status": row.get::<_, String>(3)?,
                }))
            },
        ).ok();
        result.push(serde_json::json!({
            "agent_id": agent.id,
            "name": agent.name,
            "unread": unread,
            "latest": latest,
        }));
    }
    Ok(result)
}

pub fn count_unread(pool: &DbPool, agent_id: &str) -> Result<i64, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    Ok(conn.query_row(
        "SELECT COUNT(*) FROM mailbox WHERE to_agent = ?1 AND read = 0",
        params![agent_id],
        |row| row.get(0),
    )?)
}
