use crate::db::pool::DbPool;
use rusqlite::params;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Scene {
    pub id: String,
    pub name: String,
    pub description: String,
    pub roster: String,
    pub metadata: String,
    pub created_at: String,
}

pub fn list_scenes(pool: &DbPool) -> Result<Vec<Scene>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, description, roster, metadata, created_at FROM scenes ORDER BY name"
    )?;
    let scenes = stmt.query_map([], |row| {
        Ok(Scene {
            id: row.get(0)?,
            name: row.get(1)?,
            description: row.get(2)?,
            roster: row.get(3)?,
            metadata: row.get(4)?,
            created_at: row.get(5)?,
        })
    })?
    .filter_map(|r| r.ok())
    .collect();
    Ok(scenes)
}

pub fn get_scene(pool: &DbPool, id: &str) -> Result<Option<Scene>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, description, roster, metadata, created_at FROM scenes WHERE id = ?1"
    )?;
    let mut rows = stmt.query_map(params![id], |row| {
        Ok(Scene {
            id: row.get(0)?,
            name: row.get(1)?,
            description: row.get(2)?,
            roster: row.get(3)?,
            metadata: row.get(4)?,
            created_at: row.get(5)?,
        })
    })?;
    Ok(rows.next().and_then(|r| r.ok()))
}

pub fn create_scene(
    pool: &DbPool,
    id: &str,
    name: &str,
    description: &str,
    roster: &str,
) -> Result<Scene, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO scenes (id, name, description, roster) VALUES (?1, ?2, ?3, ?4)",
        params![id, name, description, roster],
    )?;
    get_scene(pool, id).map(|s| s.unwrap())
}

pub fn delete_scene(pool: &DbPool, id: &str) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute("DELETE FROM scenes WHERE id = ?1", params![id])?;
    Ok(())
}
