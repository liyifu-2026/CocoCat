use crate::db::models::Agent;
use crate::db::pool::DbPool;

pub struct AgentManager;

impl AgentManager {
    pub fn new(_db_pool: DbPool) -> Self {
        Self
    }

    pub async fn spawn(&self, _config: &Agent) {
        // stub - will be replaced in Task 4
    }

    pub fn call_agent(
        &self,
        _agent_id: &str,
        _method: &str,
        _params: serde_json::Value,
        _timeout_secs: u64,
    ) -> Result<serde_json::Value, String> {
        Err("not implemented yet".to_string())
    }
}
