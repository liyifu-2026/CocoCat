use axum::{extract::State, Json};
use serde::{Deserialize, Serialize};

use crate::db::models::NewMessage;
use crate::db::{messages, tasks};
use crate::dispatch::engine::TaskEvent;

use super::router::AppState;

#[derive(Deserialize)]
pub struct ChatRequest {
    pub content: String,
    pub agent_id: String,
    pub scene_id: Option<String>,
    pub user_id: Option<String>,
}

#[derive(Serialize)]
pub struct ChatResponse {
    pub msg_uuid: String,
    pub task_uuid: String,
    pub assistant_content: String,
}

pub async fn chat_handler(
    State(state): State<AppState>,
    Json(req): Json<ChatRequest>,
) -> Result<Json<ChatResponse>, axum::http::StatusCode> {
    let scene_id = req.scene_id.unwrap_or_else(|| "default".to_string());

    let user_msg_uuid = uuid::Uuid::new_v4().to_string();
    let user_msg = NewMessage {
        msg_uuid: user_msg_uuid.clone(),
        agent_id: None,
        user_id: req.user_id.clone(),
        role: "user".into(),
        content: req.content.clone(),
        scene_id: scene_id.clone(),
        chat_group: "general".into(),
        metadata: "{}".into(),
    };

    messages::insert_message(&state.db_pool, &user_msg).map_err(|e| {
        tracing::error!("Failed to save user message: {}", e);
        axum::http::StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "content": req.content,
        "scene_id": scene_id,
    });

    tasks::create_task(
        &state.db_pool,
        &crate::db::models::NewTask {
            task_uuid: task_uuid.clone(),
            target_agent: req.agent_id.clone(),
            source: "web".into(),
            method: "chat".into(),
            params: params.to_string(),
        },
    )
    .map_err(|e| {
        tracing::error!("Failed to create task: {}", e);
        axum::http::StatusCode::INTERNAL_SERVER_ERROR
    })?;

    state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await.map_err(|e| {
        tracing::error!("Failed to notify dispatch engine: {}", e);
        axum::http::StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(ChatResponse {
        msg_uuid: user_msg_uuid,
        task_uuid,
        assistant_content: "Task submitted. Result will be available via polling.".into(),
    }))
}
