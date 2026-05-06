use crate::agent::process::AgentProcess;
use crate::db::models::Agent;
use crate::db::pool::DbPool;
use crate::dispatch::engine::WsEvent;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

pub struct AgentManager {
    db_pool: DbPool,
    processes: Arc<Mutex<HashMap<String, AgentProcess>>>,
}

impl AgentManager {
    pub fn new(db_pool: DbPool) -> Self {
        Self {
            db_pool,
            processes: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub async fn spawn(&self, config: &Agent) {
        let process = match AgentProcess::spawn(config) {
            Ok(p) => p,
            Err(e) => {
                tracing::error!("Failed to spawn agent {}: {}", config.id, e);
                return;
            }
        };

        let mut processes = self.processes.lock().unwrap();
        processes.insert(config.id.clone(), process);
        tracing::info!("Agent {} spawned", config.id);

        let _ = crate::db::agents::update_status(&self.db_pool, &config.id, "running");
    }

    pub fn call_agent(
        &self,
        agent_id: &str,
        method: &str,
        params: serde_json::Value,
        timeout_secs: u64,
    ) -> Result<serde_json::Value, String> {
        let mut processes = self.processes.lock()
            .map_err(|e| format!("lock error: {}", e))?;
        let process = processes.get_mut(agent_id)
            .ok_or_else(|| format!("Agent {} not found", agent_id))?;
        process.call(method, params, timeout_secs)
    }

    pub fn call_agent_stream(
        &self,
        agent_id: &str,
        method: &str,
        params: serde_json::Value,
        timeout_secs: u64,
        ws_tx: &tokio::sync::broadcast::Sender<WsEvent>,
        task_uuid: &str,
    ) -> Result<serde_json::Value, String> {
        let mut processes = self.processes.lock()
            .map_err(|e| format!("lock error: {}", e))?;
        let process = processes.get_mut(agent_id)
            .ok_or_else(|| format!("Agent {} not found", agent_id))?;
        process.call_stream(method, params, timeout_secs, ws_tx, task_uuid)
    }

    pub async fn health_check_loop(self: Arc<Self>) {
        loop {
            tokio::time::sleep(std::time::Duration::from_secs(15)).await;

            let dead_agents: Vec<String> = {
                let mut processes = match self.processes.lock() {
                    Ok(p) => p,
                    Err(_) => continue,
                };
                let mut dead = Vec::new();
                for (id, process) in processes.iter_mut() {
                    if !process.is_running() {
                        dead.push(id.clone());
                    }
                }
                dead
            };

            for id in &dead_agents {
                tracing::warn!("Agent {} is dead, removing", id);
                let _ = self.processes.lock().map(|mut p| p.remove(id));
                let _ = crate::db::agents::update_status(&self.db_pool, id, "error");
            }
        }
    }
}
