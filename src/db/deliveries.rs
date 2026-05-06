use crate::db::pool::DbPool;
use rusqlite::params;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryFile {
    pub name: String,
    pub path: String,
    pub size: i64,
    pub mime: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Delivery {
    pub id: String,
    pub subject: String,
    pub from_agent: String,
    pub body: String,
    pub files: Vec<DeliveryFile>,
    pub status: String,
    pub created_at: String,
}

pub fn create_delivery(
    pool: &DbPool, id: &str, subject: &str, from_agent: &str, body: &str, files_json: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO deliveries (id, subject, from_agent, body, files) VALUES (?1, ?2, ?3, ?4, ?5)",
        params![id, subject, from_agent, body, files_json],
    )?;
    Ok(())
}

pub fn list_deliveries(pool: &DbPool) -> Result<Vec<Delivery>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, subject, from_agent, body, files, status, created_at FROM deliveries ORDER BY created_at DESC"
    )?;
    let deliveries = stmt.query_map([], |row| {
        let files_str: String = row.get(4)?;
        let files: Vec<DeliveryFile> = serde_json::from_str(&files_str).unwrap_or_default();
        Ok(Delivery {
            id: row.get(0)?, subject: row.get(1)?, from_agent: row.get(2)?,
            body: row.get(3)?, files, status: row.get(5)?, created_at: row.get(6)?,
        })
    })?.filter_map(|r| r.ok()).collect();
    Ok(deliveries)
}

pub fn get_delivery(pool: &DbPool, id: &str) -> Result<Option<Delivery>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, subject, from_agent, body, files, status, created_at FROM deliveries WHERE id = ?1"
    )?;
    let mut rows = stmt.query_map(params![id], |row| {
        let files_str: String = row.get(4)?;
        let files: Vec<DeliveryFile> = serde_json::from_str(&files_str).unwrap_or_default();
        Ok(Delivery {
            id: row.get(0)?, subject: row.get(1)?, from_agent: row.get(2)?,
            body: row.get(3)?, files, status: row.get(5)?, created_at: row.get(6)?,
        })
    })?;
    Ok(rows.next().and_then(|r| r.ok()))
}

pub fn update_status(pool: &DbPool, id: &str, status: &str) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute("UPDATE deliveries SET status = ?1 WHERE id = ?2", params![status, id])?;
    Ok(())
}
