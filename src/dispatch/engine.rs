use std::sync::Arc;
use crate::agent::manager::AgentManager;
use crate::db::pool::DbPool;
use tokio::sync::mpsc::Receiver;

#[derive(Debug, Clone)]
pub enum TaskEvent {
    NewTask { task_uuid: String },
    Shutdown,
}

pub struct DispatchEngine;

impl DispatchEngine {
    pub fn new(
        _db_pool: DbPool,
        _agent_manager: Arc<AgentManager>,
        _rx: Receiver<TaskEvent>,
    ) -> Self {
        Self
    }

    pub async fn run(&mut self) {
        // stub
    }
}
