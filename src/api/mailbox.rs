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

pub async fn inbox_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Result<Json<Vec<MailMessage>>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let agent_id = params.get("agent_id").ok_or(StatusCode::BAD_REQUEST)?;
    let limit = params.get("limit").and_then(|v| v.parse().ok()).unwrap_or(50);
    mailbox::get_inbox(&state.db_pool, agent_id, limit).map(Json).map_err(|e| {
        tracing::error!("mailbox inbox: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })
}

pub async fn read_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(id): Path<i64>,
) -> Result<Json<()>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    mailbox::mark_read(&state.db_pool, id).map_err(|e| {
        tracing::error!("mailbox read: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(()))
}
