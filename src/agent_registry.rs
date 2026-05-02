use crate::agent_manager::AgentProcess;
use serde::Deserialize;
use std::collections::HashMap;

#[derive(Debug, Deserialize, Clone)]
pub struct AgentConfig {
    pub id: String,
    pub name: String,
    pub interpreter: String,
    pub script: String,
    pub enabled: bool,
}

#[derive(Debug, Deserialize)]
pub struct AgentsConfig {
    pub agents: Vec<AgentConfig>,
}

pub struct AgentRegistry {
    pub configs: Vec<AgentConfig>,
    processes: HashMap<String, AgentProcess>,
}

impl AgentRegistry {
    /// Load agent configurations from a TOML file
    pub fn load_config(path: &str) -> Result<Vec<AgentConfig>, String> {
        let content =
            std::fs::read_to_string(path).map_err(|e| format!("failed to read config: {}", e))?;
        let config: AgentsConfig =
            toml::from_str(&content).map_err(|e| format!("failed to parse config: {}", e))?;
        Ok(config.agents)
    }

    /// Create a new registry from configs (does not spawn)
    pub fn new(configs: Vec<AgentConfig>) -> Self {
        Self {
            configs,
            processes: HashMap::new(),
        }
    }

    /// Spawn all enabled agents
    pub fn start_all(&mut self) -> Result<(), String> {
        for config in &self.configs {
            if !config.enabled {
                continue;
            }
            let extra_args = [
                "--id",
                &config.id,
                "--name",
                &config.name,
            ];
            let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra_args)?;
            self.processes.insert(config.id.clone(), agent);
        }
        Ok(())
    }

    /// Get a mutable reference to an agent's process by id
    pub fn get(&mut self, id: &str) -> Option<&mut AgentProcess> {
        self.processes.get_mut(id)
    }

    /// Get status of all agents
    pub fn status(&self) -> Vec<AgentStatus> {
        self.configs
            .iter()
            .map(|c| AgentStatus {
                id: c.id.clone(),
                name: c.name.clone(),
                enabled: c.enabled,
                running: self.processes.contains_key(&c.id),
            })
            .collect()
    }

    /// Stop all agents and clear the registry
    pub fn stop_all(&mut self) {
        self.processes.clear();
    }
}

#[derive(Debug)]
pub struct AgentStatus {
    pub id: String,
    pub name: String,
    pub enabled: bool,
    pub running: bool,
}
