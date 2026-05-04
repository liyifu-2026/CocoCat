use crate::db::pool::DbPool;
use rusqlite::params;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HireRequest {
    pub id: i64,
    pub request_uuid: String,
    pub requester_agent: String,
    pub new_agent_id: String,
    pub new_agent_name: String,
    pub new_agent_role: String,
    pub reason: String,
    pub status: String,
    pub reviewer: Option<String>,
    pub created_at: String,
    pub decided_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewHireRequest {
    pub request_uuid: String,
    pub requester_agent: String,
    pub new_agent_id: String,
    pub new_agent_name: String,
    pub new_agent_role: String,
    pub reason: String,
}

pub fn create_request(
    pool: &DbPool,
    req: &NewHireRequest,
) -> Result<HireRequest, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO hire_requests (request_uuid, requester_agent, new_agent_id, new_agent_name, new_agent_role, reason, status)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'pending')",
        params![req.request_uuid, req.requester_agent, req.new_agent_id, req.new_agent_name, req.new_agent_role, req.reason],
    )?;
    let id = conn.last_insert_rowid();
    get_request(pool, id)
}

fn get_request(pool: &DbPool, id: i64) -> Result<HireRequest, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    Ok(conn.query_row(
        "SELECT id, request_uuid, requester_agent, new_agent_id, new_agent_name, new_agent_role,
                reason, status, reviewer, created_at, decided_at
         FROM hire_requests WHERE id = ?1",
        params![id],
        |row| {
            Ok(HireRequest {
                id: row.get(0)?,
                request_uuid: row.get(1)?,
                requester_agent: row.get(2)?,
                new_agent_id: row.get(3)?,
                new_agent_name: row.get(4)?,
                new_agent_role: row.get(5)?,
                reason: row.get(6)?,
                status: row.get(7)?,
                reviewer: row.get(8)?,
                created_at: row.get(9)?,
                decided_at: row.get(10)?,
            })
        },
    )?)
}

pub fn list_pending(pool: &DbPool) -> Result<Vec<HireRequest>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, request_uuid, requester_agent, new_agent_id, new_agent_name, new_agent_role,
                reason, status, reviewer, created_at, decided_at
         FROM hire_requests WHERE status = 'pending'
         ORDER BY created_at ASC"
    )?;
    let requests = stmt.query_map([], |row| {
        Ok(HireRequest {
            id: row.get(0)?,
            request_uuid: row.get(1)?,
            requester_agent: row.get(2)?,
            new_agent_id: row.get(3)?,
            new_agent_name: row.get(4)?,
            new_agent_role: row.get(5)?,
            reason: row.get(6)?,
            status: row.get(7)?,
            reviewer: row.get(8)?,
            created_at: row.get(9)?,
            decided_at: row.get(10)?,
        })
    })?
    .filter_map(|r| r.ok())
    .collect();
    Ok(requests)
}

pub fn approve_request(
    pool: &DbPool,
    request_uuid: &str,
    reviewer: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE hire_requests SET status = 'approved', reviewer = ?1, decided_at = datetime('now')
         WHERE request_uuid = ?2",
        params![reviewer, request_uuid],
    )?;

    // Auto-create the agent
    let request = conn.query_row(
        "SELECT new_agent_id, new_agent_name, new_agent_role FROM hire_requests WHERE request_uuid = ?1",
        params![request_uuid],
        |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?, row.get::<_, String>(2)?)),
    )?;

    conn.execute(
        "INSERT OR IGNORE INTO agents (id, name, role, model, scene_id, status, metadata)
         VALUES (?1, ?2, ?3, 'gpt-4', 'default', 'stopped', '{}')",
        params![request.0, request.1, request.2],
    )?;

    Ok(())
}

pub fn reject_request(
    pool: &DbPool,
    request_uuid: &str,
    reviewer: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE hire_requests SET status = 'rejected', reviewer = ?1, decided_at = datetime('now')
         WHERE request_uuid = ?2",
        params![reviewer, request_uuid],
    )?;
    Ok(())
}
