use std::sync::Arc;

use crate::agent::manager::AgentManager;
use crate::db::pool::DbPool;
use crate::db::tasks;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::sync::broadcast;
use tokio::sync::mpsc::Receiver;

#[derive(Debug, Clone)]
pub enum TaskEvent {
    NewTask { task_uuid: String },
    Shutdown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsEvent {
    pub event: String,
    pub task_uuid: String,
    pub status: String,
    pub result: Option<Value>,
    pub error: Option<String>,
}

pub struct DispatchEngine {
    db_pool: DbPool,
    agent_manager: Arc<AgentManager>,
    rx: Receiver<TaskEvent>,
    ws_tx: broadcast::Sender<WsEvent>,
}

impl DispatchEngine {
    pub fn new(
        db_pool: DbPool,
        agent_manager: Arc<AgentManager>,
        rx: Receiver<TaskEvent>,
        ws_tx: broadcast::Sender<WsEvent>,
    ) -> Self {
        Self {
            db_pool,
            agent_manager,
            rx,
            ws_tx,
        }
    }

    pub async fn run(&mut self) {
        tracing::info!("Dispatch engine started");

        loop {
            tokio::select! {
                Some(event) = self.rx.recv() => {
                    match event {
                        TaskEvent::NewTask { task_uuid } => {
                            let db = self.db_pool.clone();
                            let mgr = self.agent_manager.clone();
                            let ws = self.ws_tx.clone();
                            let uuid = task_uuid.clone();
                            tokio::spawn(async move {
                                if let Err(e) = process_task(&db, &mgr, &ws, &uuid).await {
                                    tracing::error!("Failed to process task {}: {}", uuid, e);
                                }
                            });
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
}

async fn process_task(
    db_pool: &DbPool,
    agent_manager: &Arc<AgentManager>,
    ws_tx: &broadcast::Sender<WsEvent>,
    task_uuid: &str,
) -> Result<(), String> {
    let (target, method, params) = {
        let task = tasks::claim_pending_task(db_pool)
            .map_err(|e| format!("claim task: {}", e))?
            .ok_or_else(|| format!("Task {} not found or already claimed", task_uuid))?;

        let params: Value = serde_json::from_str(&task.params)
            .map_err(|e| format!("parse params: {}", e))?;

        (task.target_agent, task.method, params)
    };

    tracing::info!("Dispatching task {} to agent {}", task_uuid, target);

    let manager = agent_manager.clone();
    let call_result = tokio::task::spawn_blocking(move || {
        manager.call_agent(&target, &method, params, 120)
    })
    .await
    .map_err(|e| format!("join error: {}", e))?;

    match call_result {
        Ok(result) => {
            let result_str = serde_json::to_string(&result)
                .map_err(|e| format!("serialize result: {}", e))?;

            tasks::complete_task(db_pool, task_uuid, &result_str)
                .map_err(|e| format!("complete task: {}", e))?;

            let _ = ws_tx.send(WsEvent {
                event: "task_completed".into(),
                task_uuid: task_uuid.to_string(),
                status: "completed".into(),
                result: Some(result),
                error: None,
            });

            tracing::info!("Task {} completed successfully", task_uuid);
        }
        Err(e) => {
            tasks::fail_task(db_pool, task_uuid, &e)
                .map_err(|e2| format!("fail task: {}", e2))?;

            let _ = ws_tx.send(WsEvent {
                event: "task_failed".into(),
                task_uuid: task_uuid.to_string(),
                status: "failed".into(),
                result: None,
                error: Some(e.clone()),
            });

            tracing::error!("Task {} failed: {}", task_uuid, e);
        }
    }

    Ok(())
}
