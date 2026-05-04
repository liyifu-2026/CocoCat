use std::sync::Arc;

use crate::agent::manager::AgentManager;
use crate::db::pool::DbPool;
use crate::db::tasks;
use serde_json::Value;
use tokio::sync::mpsc::Receiver;

#[derive(Debug, Clone)]
pub enum TaskEvent {
    NewTask { task_uuid: String },
    Shutdown,
}

pub struct DispatchEngine {
    db_pool: DbPool,
    agent_manager: Arc<AgentManager>,
    rx: Receiver<TaskEvent>,
}

impl DispatchEngine {
    pub fn new(
        db_pool: DbPool,
        agent_manager: Arc<AgentManager>,
        rx: Receiver<TaskEvent>,
    ) -> Self {
        Self {
            db_pool,
            agent_manager,
            rx,
        }
    }

    pub async fn run(&mut self) {
        tracing::info!("Dispatch engine started");

        loop {
            tokio::select! {
                Some(event) = self.rx.recv() => {
                    match event {
                        TaskEvent::NewTask { task_uuid } => {
                            if let Err(e) = self.process_task(&task_uuid).await {
                                tracing::error!("Failed to process task {}: {}", task_uuid, e);
                            }
                        }
                        TaskEvent::Shutdown => {
                            tracing::info!("Dispatch engine shutting down");
                            break;
                        }
                    }
                }
                else => {
                    tracing::warn!("Task channel closed");
                    break;
                }
            }
        }
    }

    async fn process_task(&self, task_uuid: &str) -> Result<(), String> {
        let (target, method, params) = {
            let task = tasks::claim_pending_task(&self.db_pool)
                .map_err(|e| format!("claim task: {}", e))?
                .ok_or_else(|| format!("Task {} not found or already claimed", task_uuid))?;

            let params: Value = serde_json::from_str(&task.params)
                .map_err(|e| format!("parse params: {}", e))?;

            (task.target_agent, task.method, params)
        };

        tracing::info!("Dispatching task {} to agent {}", task_uuid, target);

        let manager = self.agent_manager.clone();
        let result = tokio::task::spawn_blocking(move || {
            manager.call_agent(&target, &method, params, 120)
        })
        .await
        .map_err(|e| format!("join error: {}", e))?
        .map_err(|e| {
            let _ = tasks::fail_task(&self.db_pool, task_uuid, &e);
            e
        })?;

        let result_str = serde_json::to_string(&result)
            .map_err(|e| format!("serialize result: {}", e))?;

        tasks::complete_task(&self.db_pool, task_uuid, &result_str)
            .map_err(|e| format!("complete task: {}", e))?;

        tracing::info!("Task {} completed successfully", task_uuid);
        Ok(())
    }
}
