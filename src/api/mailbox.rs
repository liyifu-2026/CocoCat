use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;

use crate::auth;
use crate::db::mailbox::{self, MailMessage, NewMailMessage};
use crate::db::models::NewTask;
use crate::db::tasks;
use crate::dispatch::engine::TaskEvent;

use super::router::AppState;

#[derive(Deserialize)]
pub struct SendRequest {
    pub from_agent: String,
    pub to_agent: String,
    pub subject: String,
    pub body: String,
}

pub async fn list_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let mailboxes = mailbox::list_inboxes(&state.db_pool).map_err(|e| {
        tracing::error!("mailbox list: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "mailboxes": mailboxes })))
}

pub async fn get_messages_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let messages = mailbox::get_inbox(&state.db_pool, &agent_id, 100).map_err(|e| {
        tracing::error!("mailbox messages: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    let messages_json: Vec<serde_json::Value> = messages
        .iter()
        .map(|m| {
            serde_json::json!({
                "from": m.from_agent,
                "content": m.body,
                "timestamp": m.created_at,
                "status": if m.read == 1 { "read" } else { "unread" },
            })
        })
        .collect();
    Ok(Json(serde_json::json!({ "messages": messages_json })))
}

pub async fn send_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<SendRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let msg = NewMailMessage {
        msg_uuid: uuid::Uuid::new_v4().to_string(),
        from_agent: req.from_agent.clone(),
        to_agent: req.to_agent.clone(),
        subject: req.subject.clone(),
        body: req.body.clone(),
    };
    let saved = mailbox::send_message(&state.db_pool, &msg).map_err(|e| {
        tracing::error!("mailbox send: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Create a task to deliver this mailbox message to the target agent
    let task_uuid = uuid::Uuid::new_v4().to_string();
    let task = NewTask {
        task_uuid: task_uuid.clone(),
        target_agent: req.to_agent,
        source: req.from_agent,
        method: "mailbox".into(),
        params: serde_json::json!({
            "mailbox_msg_id": saved.msg_uuid,
            "subject": req.subject,
            "content": req.body,
        }).to_string(),
        ..Default::default()
    };
    if tasks::create_task(&state.db_pool, &task).is_ok() {
        let _ = state.task_tx.send(TaskEvent::NewTask { task_uuid }).await;
    }

    Ok(Json(serde_json::json!(saved)))
}

pub async fn mark_read_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    mailbox::mark_all_read(&state.db_pool, &agent_id).map_err(|e| {
        tracing::error!("mailbox mark_read: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "status": "ok" })))
}
