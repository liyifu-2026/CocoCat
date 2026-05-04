use crate::db::models::Agent;
use crate::db::pool::DbPool;
use rusqlite::params;

pub fn load_agents(pool: &DbPool) -> Result<Vec<Agent>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, role, model, scene_id, status,
                system_prompt, metadata, created_at, last_heartbeat_at
         FROM agents WHERE status != 'stopped'"
    )?;

    let agents = stmt.query_map([], |row| {
        Ok(Agent {
            id: row.get(0)?,
            name: row.get(1)?,
            role: row.get(2)?,
            model: row.get(3)?,
            scene_id: row.get(4)?,
            status: row.get(5)?,
            system_prompt: row.get(6)?,
            metadata: row.get(7)?,
            created_at: row.get(8)?,
            last_heartbeat_at: row.get(9)?,
        })
    })?
    .filter_map(|r| r.ok())
    .collect();

    Ok(agents)
}

pub fn update_status(
    pool: &DbPool,
    agent_id: &str,
    status: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "UPDATE agents SET status = ?1, last_heartbeat_at = datetime('now') WHERE id = ?2",
        params![status, agent_id],
    )?;
    Ok(())
}

pub fn get_agent(pool: &DbPool, agent_id: &str) -> Result<Option<Agent>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, name, role, model, scene_id, status,
                system_prompt, metadata, created_at, last_heartbeat_at
         FROM agents WHERE id = ?1"
    )?;

    let mut rows = stmt.query_map(params![agent_id], |row| {
        Ok(Agent {
            id: row.get(0)?,
            name: row.get(1)?,
            role: row.get(2)?,
            model: row.get(3)?,
            scene_id: row.get(4)?,
            status: row.get(5)?,
            system_prompt: row.get(6)?,
            metadata: row.get(7)?,
            created_at: row.get(8)?,
            last_heartbeat_at: row.get(9)?,
        })
    })?;

    Ok(rows.next().and_then(|r| r.ok()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::pool::create_test_pool;

    #[test]
    fn test_load_agents_empty() {
        let pool = create_test_pool();
        let agents = load_agents(&pool).unwrap();
        assert!(agents.is_empty());
    }

    #[test]
    fn test_update_status() {
        let pool = create_test_pool();
        let conn = pool.get().unwrap();
        conn.execute(
            "INSERT INTO agents (id, name, role, model, status) VALUES (?1, ?2, ?3, ?4, ?5)",
            params!["test_agent", "Test", "worker", "gpt-4", "stopped"],
        ).unwrap();
        drop(conn);

        update_status(&pool, "test_agent", "running").unwrap();

        let agent = get_agent(&pool, "test_agent").unwrap().unwrap();
        assert_eq!(agent.status, "running");
    }
}
