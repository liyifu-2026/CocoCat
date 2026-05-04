use crate::db::pool::DbPool;
use rusqlite::params;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Skill {
    pub id: String,
    pub name: String,
    pub scope: String,
    pub content: String,
    pub scene_id: Option<String>,
    pub agent_id: Option<String>,
    pub created_at: String,
}

pub fn list_skills(pool: &DbPool, scope: Option<&str>) -> Result<Vec<Skill>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = if let Some(s) = scope {
        let mut stmt = conn.prepare(
            "SELECT id, name, scope, content, scene_id, agent_id, created_at
             FROM skills WHERE scope = ?1 ORDER BY name"
        )?;
        let skills = stmt.query_map(params![s], row_to_skill)?
            .filter_map(|r| r.ok())
            .collect();
        return Ok(skills);
    } else {
        conn.prepare(
            "SELECT id, name, scope, content, scene_id, agent_id, created_at
             FROM skills ORDER BY name"
        )?
    };

    let skills = stmt.query_map([], row_to_skill)?
        .filter_map(|r| r.ok())
        .collect();
    Ok(skills)
}

fn row_to_skill(row: &rusqlite::Row) -> rusqlite::Result<Skill> {
    Ok(Skill {
        id: row.get(0)?,
        name: row.get(1)?,
        scope: row.get(2)?,
        content: row.get(3)?,
        scene_id: row.get(4)?,
        agent_id: row.get(5)?,
        created_at: row.get(6)?,
    })
}

pub fn get_skill(pool: &DbPool, id: &str) -> Result<Option<Skill>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, scope, content, scene_id, agent_id, created_at FROM skills WHERE id = ?1"
    )?;
    let mut rows = stmt.query_map(params![id], row_to_skill)?;
    Ok(rows.next().and_then(|r| r.ok()))
}

pub fn create_skill(
    pool: &DbPool,
    id: &str,
    name: &str,
    scope: &str,
    content: &str,
) -> Result<Skill, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO skills (id, name, scope, content) VALUES (?1, ?2, ?3, ?4)",
        params![id, name, scope, content],
    )?;
    get_skill(pool, id).map(|s| s.unwrap())
}
