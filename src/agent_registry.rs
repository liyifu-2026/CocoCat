use crate::agent_manager::AgentProcess;
use crate::transport;
use serde::Deserialize;
use std::collections::HashMap;

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

    /// Dispatch a message to a target agent by id.
    /// Writes the dispatch to the agent's .msg file and sends a task call.
    pub fn dispatch_message(
        &mut self,
        target_id: &str,
        method: &str,
        params: Option<serde_json::Value>,
    ) -> Result<transport::JsonRpcResponse, String> {
        let agent = self.processes.get_mut(target_id).ok_or_else(|| {
            format!("agent '{}' not found or not running", target_id)
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
                    let _ = writeln!(file, "{}", msg_content);
                }
            }
        }

        // Send the task call to the agent
        agent.call(method, params, 0)
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
