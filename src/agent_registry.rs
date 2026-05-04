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
