use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;

use crate::auth;
use crate::db::mailbox::{self, MailMessage, NewMailMessage};

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
) -> Result<Json<MailMessage>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let msg = NewMailMessage {
        msg_uuid: uuid::Uuid::new_v4().to_string(),
        from_agent: req.from_agent,
        to_agent: req.to_agent,
        subject: req.subject,
        body: req.body,
    };
    mailbox::send_message(&state.db_pool, &msg).map(Json).map_err(|e| {
        tracing::error!("mailbox send: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })
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
