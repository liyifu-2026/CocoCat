use crate::db::pool::DbPool;
use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Deserialize)]
struct AgentConfig {
    id: String,
    name: String,
    interpreter: Option<String>,
    script: Option<String>,
    enabled: Option<bool>,
    scene: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ConfigFile {
    agents: Vec<AgentConfig>,
}

pub fn seed_from_config_toml(pool: &DbPool) -> Result<(), Box<dyn std::error::Error>> {
    let path = "agents/config.toml";
    if !Path::new(path).exists() {
        tracing::warn!("Config file not found: {}", path);
        return Ok(());
    }

    let content = std::fs::read_to_string(path)?;
    let config: ConfigFile = toml::from_str(&content)?;

    let conn = pool.get()?;
    let mut seeded = 0;

    for agent in &config.agents {
        if agent.enabled == Some(false) {
            continue;
        }

        // Check if already exists
        let exists: bool = conn
            .query_row(
                "SELECT COUNT(*) > 0 FROM agents WHERE id = ?1",
                rusqlite::params![agent.id],
                |row| row.get(0),
            )
            .unwrap_or(false);

        if exists {
            tracing::debug!("Agent {} already seeded, skipping", agent.id);
            continue;
        }

        conn.execute(
            "INSERT INTO agents (id, name, role, model, scene_id, status, metadata)
             VALUES (?1, ?2, 'worker', 'gpt-4', ?3, 'running', '{}')",
            rusqlite::params![agent.id, agent.name, agent.scene.as_deref().unwrap_or("default")],
        )?;

        seeded += 1;
        tracing::info!("Seeded agent: {} ({})", agent.id, agent.name);
    }

    if seeded > 0 {
        tracing::info!("Seeded {} agents from config.toml", seeded);
    }

    Ok(())
}
