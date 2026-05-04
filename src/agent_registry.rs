use crate::agent_manager::AgentProcess;
use crate::errors::AgentError;
use cococat::transport;
use serde::Deserialize;
use std::collections::HashMap;
use std::time::Instant;

#[derive(Debug, Deserialize, Clone)]
pub struct AgentConfig {
    pub id: String,
    pub name: String,
    pub interpreter: String,
    pub script: String,
    pub enabled: bool,
    pub scene: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct AgentsConfig {
    pub agents: Vec<AgentConfig>,
}

struct RestartState {
    retry_count: u32,
    backoff_until: Instant,
    consecutive_successes: u32,
}

pub struct AgentRegistry {
    pub configs: Vec<AgentConfig>,
    pub processes: HashMap<String, AgentProcess>,
    restart_states: HashMap<String, RestartState>,
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
            restart_states: HashMap::new(),
        }
    }

    /// Spawn all enabled agents
    pub fn start_all(&mut self) -> Result<(), String> {
        for config in &self.configs {
            if !config.enabled {
                continue;
            }
            let mut extra_args: Vec<&str> = vec!["--id", &config.id, "--name", &config.name];
            if let Some(scene) = &config.scene {
                extra_args.push("--scene");
                extra_args.push(scene);
            }
            let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra_args)?;
            self.processes.insert(config.id.clone(), agent);
        }
        Ok(())
    }

    pub fn start_one(&mut self, config: AgentConfig) -> Result<(), String> {
        if !config.enabled {
            return Ok(());
        }
        let extra = ["--id", &config.id, "--name", &config.name];
        let agent = AgentProcess::spawn(&config.interpreter, &config.script, &extra)?;
        self.processes.insert(config.id.clone(), agent);
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
    #[allow(dead_code)]
    pub fn stop_all(&mut self) {
        self.processes.clear();
    }

    /// Remove a dead agent's entry from the processes map
    fn remove_dead(&mut self, id: &str) {
        self.processes.remove(id);
    }

    /// Restart a single agent by config
    pub fn restart_one(&mut self, id: &str) -> Result<(), String> {
        self.remove_dead(id);
        let config = self.configs.iter()
            .find(|c| c.id == id)
            .ok_or_else(|| format!("config not found for {}", id))?;
        if !config.enabled {
            return Err(format!("agent {} is disabled", id));
        }
        self.start_one(config.clone())?;
        Ok(())
    }

    /// Health check: ping each running agent, restart dead ones with backoff. Returns list of restarted agents.
    pub fn health_check(&mut self) -> Vec<String> {
        let mut restarted = Vec::new();
        let ids: Vec<String> = self.processes.keys().cloned().collect();

        for id in ids {
            let now = Instant::now();

            if let Some(state) = self.restart_states.get(&id) {
                if now < state.backoff_until {
                    continue;
                }
            }

            let running = self.processes.get_mut(&id)
                .map(|p| p.is_running())
                .unwrap_or(false);

            if running {
                if let Some(state) = self.restart_states.get_mut(&id) {
                    state.consecutive_successes += 1;
                    if state.consecutive_successes >= 3 {
                        state.retry_count = 0;
                    }
                }
            } else {
                self.remove_dead(&id);

                let state = self.restart_states.entry(id.clone()).or_insert(RestartState {
                    retry_count: 0,
                    backoff_until: now,
                    consecutive_successes: 0,
                });
                state.retry_count += 1;
                state.consecutive_successes = 0;
                let backoff_secs = std::cmp::min(
                    5u64 * (1u64 << state.retry_count.min(6)),
                    300,
                );
                state.backoff_until = now + std::time::Duration::from_secs(backoff_secs);

                tracing::warn!("Agent '{id}' is dead, restarting...");
                match self.restart_one(&id) {
                    Ok(()) => {
                        tracing::info!("Agent '{id}' restarted successfully");
                        restarted.push(id);
                    }
                    Err(e) => {
                        tracing::error!("Failed to restart agent '{id}': {e}");
                    }
                }
            }
        }
        restarted
    }

    /// Dispatch a message to a target agent by id.
    /// Writes the dispatch to the agent's .msg file and sends a task call.
    pub fn dispatch_message(
        &mut self,
        target_id: &str,
        method: &str,
        params: Option<serde_json::Value>,
    ) -> Result<transport::JsonRpcResponse, AgentError> {
        let agent = self.processes.get_mut(target_id).ok_or_else(|| {
            AgentError::ConfigError(format!("agent '{}' not found or not running", target_id))
        })?;

        // Write the dispatch message to the agent's .msg file
        if let Some(ref p) = params {
            if let Some(prompt) = p.get("prompt").and_then(|v| v.as_str()) {
                let timestamp = chrono::Utc::now().to_rfc3339();
                let msg_content = format!(
                    "{{sender: leader, timestamp: {}, content: {}}}",
                    timestamp, prompt
                );
                let msg_path = format!("agents/dispatch_messages/{}.msg", target_id);
                if let Ok(mut file) = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(&msg_path)
                {
                    use std::io::Write;
                    if let Err(e) = writeln!(file, "{}", msg_content) {
                        tracing::warn!("Failed to write dispatch message: {e}");
                    }
                }
            }
        }

        // Send the task call to the agent
        agent.call(method, params, 0, 60)
    }
}

#[allow(dead_code)]
#[derive(Debug)]
pub struct AgentStatus {
    pub id: String,
    pub name: String,
    pub enabled: bool,
    pub running: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_config_file_not_found() {
        let result = AgentRegistry::load_config("/nonexistent/config.toml");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("failed to read config"));
    }

    #[test]
    fn test_new_registry_empty() {
        let registry = AgentRegistry::new(vec![]);
        assert!(registry.configs.is_empty());
        assert!(registry.processes.is_empty());
    }

    #[test]
    fn test_new_registry_with_configs() {
        let configs = vec![
            AgentConfig {
                id: "agent_1".to_string(),
                name: "Agent 1".to_string(),
                interpreter: "python".to_string(),
                script: "script.py".to_string(),
                enabled: true,
                scene: None,
            },
        ];
        let registry = AgentRegistry::new(configs);
        assert_eq!(registry.configs.len(), 1);
        assert_eq!(registry.configs[0].id, "agent_1");
    }

    #[test]
    fn test_status_reflects_config() {
        let configs = vec![
            AgentConfig {
                id: "alpha".to_string(), name: "Alpha".to_string(),
                interpreter: "python".to_string(), script: "run.py".to_string(),
                enabled: true, scene: None,
            },
            AgentConfig {
                id: "beta".to_string(), name: "Beta".to_string(),
                interpreter: "python".to_string(), script: "run.py".to_string(),
                enabled: false, scene: None,
            },
        ];
        let registry = AgentRegistry::new(configs);
        let statuses = registry.status();
        assert_eq!(statuses.len(), 2);
        assert!(statuses[0].enabled);
        assert!(!statuses[1].enabled);
        assert!(!statuses[0].running);
        assert!(!statuses[1].running);
    }

    #[test]
    fn test_get_unknown_agent() {
        let mut registry = AgentRegistry::new(vec![]);
        assert!(registry.get("nonexistent").is_none());
    }

    #[test]
    fn test_remove_dead_nonexistent() {
        let mut registry = AgentRegistry::new(vec![]);
        registry.remove_dead("ghost");
    }

    #[test]
    fn test_restart_one_no_config() {
        let mut registry = AgentRegistry::new(vec![]);
        let result = registry.restart_one("nonexistent");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("config not found"));
    }

    #[test]
    fn test_restart_one_disabled() {
        let configs = vec![
            AgentConfig {
                id: "idle".to_string(), name: "Idle".to_string(),
                interpreter: "python".to_string(), script: "run.py".to_string(),
                enabled: false, scene: None,
            },
        ];
        let mut registry = AgentRegistry::new(configs);
        let result = registry.restart_one("idle");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("disabled"));
    }

    #[test]
    fn test_dispatch_message_unknown_agent() {
        let mut registry = AgentRegistry::new(vec![]);
        let result = registry.dispatch_message("ghost", "task", None);
        assert!(result.is_err());
        match result {
            Err(AgentError::ConfigError(msg)) => assert!(msg.contains("ghost")),
            _ => panic!("expected ConfigError"),
        }
    }

    #[test]
    fn test_health_check_empty_registry() {
        let mut registry = AgentRegistry::new(vec![]);
        let restarted = registry.health_check();
        assert!(restarted.is_empty());
    }

    #[test]
    fn test_health_check_no_running_agents() {
        let configs = vec![
            AgentConfig {
                id: "offline".to_string(), name: "Offline".to_string(),
                interpreter: "python".to_string(), script: "run.py".to_string(),
                enabled: true, scene: None,
            },
        ];
        let mut registry = AgentRegistry::new(configs);
        let restarted = registry.health_check();
        // No processes started, so health check has nothing to check
        assert!(restarted.is_empty());
    }
}
