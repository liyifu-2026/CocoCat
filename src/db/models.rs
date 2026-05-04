use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    pub id: String,
    pub name: String,
    pub role: String,
    pub model: String,
    pub scene_id: String,
    pub status: String,
    pub system_prompt: String,
    pub metadata: String,
    pub created_at: String,
    pub last_heartbeat_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub id: i64,
    pub msg_uuid: String,
    pub agent_id: Option<String>,
    pub user_id: Option<String>,
    pub role: String,
    pub content: String,
    pub scene_id: String,
    pub chat_group: String,
    pub metadata: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: i64,
    pub task_uuid: String,
    pub target_agent: String,
    pub source: String,
    pub method: String,
    pub params: String,
    pub status: String,
    pub result: Option<String>,
    pub error: Option<String>,
    pub retry_count: i32,
    pub max_retries: i32,
    pub created_at: String,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewMessage {
    pub msg_uuid: String,
    pub agent_id: Option<String>,
    pub user_id: Option<String>,
    pub role: String,
    pub content: String,
    pub scene_id: String,
    pub chat_group: String,
    pub metadata: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewTask {
    pub task_uuid: String,
    pub target_agent: String,
    pub source: String,
    pub method: String,
    pub params: String,
}
