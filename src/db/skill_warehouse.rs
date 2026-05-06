use crate::db::pool::DbPool;
use rusqlite::params;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillRecord {
    pub id: String,
    pub name: String,
    pub description: String,
    pub content: String,
    pub version: String,
    pub source: String,
    pub source_url: Option<String>,
    pub author: String,
    pub tags: String,
    pub deps: String,
    pub created_at: String,
    pub updated_at: String,
}

pub fn list_warehouse(pool: &DbPool) -> Result<Vec<SkillRecord>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, description, content, version, source, source_url,
                author, tags, deps, created_at, updated_at
         FROM skill_warehouse ORDER BY name"
    )?;
    let rows = stmt.query_map([], row_to_skill)?;
    let mut skills = Vec::new();
    for r in rows {
        skills.push(r?);
    }
    Ok(skills)
}

pub fn get_warehouse_skill(pool: &DbPool, id: &str) -> Result<Option<SkillRecord>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, description, content, version, source, source_url,
                author, tags, deps, created_at, updated_at
         FROM skill_warehouse WHERE id = ?1"
    )?;
    let mut rows = stmt.query_map(params![id], row_to_skill)?;
    Ok(rows.next().and_then(|r| r.ok()))
}

pub fn upsert_warehouse_skill(
    pool: &DbPool,
    id: &str,
    name: &str,
    description: &str,
    content: &str,
    source: &str,
    source_url: Option<&str>,
    author: &str,
    tags: &str,
    deps: &str,
) -> Result<SkillRecord, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO skill_warehouse (id, name, description, content, version, source, source_url, author, tags, deps)
         VALUES (?1, ?2, ?3, ?4, '1.0', ?5, ?6, ?7, ?8, ?9)
         ON CONFLICT(id) DO UPDATE SET
           name=excluded.name, description=excluded.description, content=excluded.content,
           source=excluded.source, source_url=excluded.source_url, author=excluded.author,
           tags=excluded.tags, deps=excluded.deps, updated_at=datetime('now')",
        params![id, name, description, content, source, source_url, author, tags, deps],
    )?;
    get_warehouse_skill(pool, id).map(|s| s.unwrap())
}

pub fn delete_warehouse_skill(pool: &DbPool, id: &str) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute("DELETE FROM agent_skills WHERE skill_id = ?1", params![id])?;
    conn.execute("DELETE FROM skill_warehouse WHERE id = ?1", params![id])?;
    Ok(())
}

// --- Agent-Skill assignment ---

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSkillRow {
    pub agent_id: String,
    pub skill_id: String,
    pub enabled: i32,
    pub assigned_at: String,
}

pub fn get_agent_skills(pool: &DbPool, agent_id: &str) -> Result<Vec<serde_json::Value>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT s.id, s.name, s.description, s.source, s.tags, a_s.enabled
         FROM agent_skills a_s
         JOIN skill_warehouse s ON s.id = a_s.skill_id
         WHERE a_s.agent_id = ?1
         ORDER BY s.name"
    )?;
    let rows = stmt.query_map(params![agent_id], |row| {
        Ok(serde_json::json!({
            "id": row.get::<_, String>(0)?,
            "name": row.get::<_, String>(1)?,
            "description": row.get::<_, String>(2)?,
            "source": row.get::<_, String>(3)?,
            "tags": row.get::<_, String>(4)?,
            "enabled": row.get::<_, i32>(5)?,
        }))
    })?;
    let mut skills = Vec::new();
    for r in rows {
        skills.push(r?);
    }
    Ok(skills)
}

pub fn set_agent_skills(
    pool: &DbPool,
    agent_id: &str,
    skill_ids: &[String],
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute("DELETE FROM agent_skills WHERE agent_id = ?1", params![agent_id])?;
    for sid in skill_ids {
        conn.execute(
            "INSERT OR IGNORE INTO agent_skills (agent_id, skill_id) VALUES (?1, ?2)",
            params![agent_id, sid],
        )?;
    }
    Ok(())
}

pub fn auto_assign_builtin(pool: &DbPool) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let agent_ids: Vec<String> = {
        let mut stmt = conn.prepare("SELECT id FROM agents WHERE status != 'stopped'")?;
        let rows: Vec<String> = stmt.query_map([], |row| row.get(0))?
            .filter_map(|r| r.ok())
            .collect();
        rows
    };
    let builtin_ids: Vec<String> = {
        let mut stmt = conn.prepare(
            "SELECT id FROM skill_warehouse WHERE source = 'builtin'"
        )?;
        let rows: Vec<String> = stmt.query_map([], |row| row.get(0))?
            .filter_map(|r| r.ok())
            .collect();
        rows
    };
    for aid in &agent_ids {
        for sid in &builtin_ids {
            conn.execute(
                "INSERT OR IGNORE INTO agent_skills (agent_id, skill_id) VALUES (?1, ?2)",
                params![aid, sid],
            ).ok();
        }
    }
    Ok(())
}

pub fn capabilities(pool: &DbPool) -> Result<Vec<serde_json::Value>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT a.id, a.name, a.role, a.status
         FROM agents a WHERE a.status != 'stopped' ORDER BY a.name"
    )?;
    let agents = stmt.query_map([], |row| {
        Ok(serde_json::json!({
            "agent_id": row.get::<_, String>(0)?,
            "name": row.get::<_, String>(1)?,
            "role": row.get::<_, String>(2)?,
            "status": row.get::<_, String>(3)?,
        }))
    })?;
    let mut result: Vec<serde_json::Value> = Vec::new();
    for a in agents {
        let a = a?;
        let agent_id = a.get("agent_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let skills = get_agent_skills(pool, &agent_id).unwrap_or_default();
        let mut entry = a;
        entry["skills"] = serde_json::Value::Array(skills);
        result.push(entry);
    }
    Ok(result)
}

fn row_to_skill(row: &rusqlite::Row) -> rusqlite::Result<SkillRecord> {
    Ok(SkillRecord {
        id: row.get(0)?,
        name: row.get(1)?,
        description: row.get(2)?,
        content: row.get(3)?,
        version: row.get(4)?,
        source: row.get(5)?,
        source_url: row.get(6)?,
        author: row.get(7)?,
        tags: row.get(8)?,
        deps: row.get(9)?,
        created_at: row.get(10)?,
        updated_at: row.get(11)?,
    })
}
