use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};

use crate::auth;
use crate::db::hire::{self, HireRequest, NewHireRequest};

use super::router::AppState;

#[derive(Deserialize)]
pub struct CreateRequest {
    pub requester_agent: String,
    pub new_agent_id: String,
    pub new_agent_name: String,
    pub new_agent_role: String,
    pub reason: String,
}

#[derive(Serialize)]
pub struct HireResponse {
    pub request_uuid: String,
    pub status: String,
}

pub async fn create_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<CreateRequest>,
) -> Result<Json<HireResponse>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let request_uuid = uuid::Uuid::new_v4().to_string();
    let new_req = NewHireRequest {
        request_uuid: request_uuid.clone(),
        requester_agent: req.requester_agent,
        new_agent_id: req.new_agent_id,
        new_agent_name: req.new_agent_name,
        new_agent_role: req.new_agent_role,
        reason: req.reason,
    };
    hire::create_request(&state.db_pool, &new_req).map_err(|e| {
        tracing::error!("hire create: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(HireResponse {
        request_uuid,
        status: "pending".into(),
    }))
}

pub async fn list_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
) -> Result<Json<Vec<HireRequest>>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    hire::list_pending(&state.db_pool).map_err(|e| {
        tracing::error!("hire list: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    }).map(Json)
}

pub async fn approve_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(request_uuid): Path<String>,
) -> Result<Json<()>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    hire::approve_request(&state.db_pool, &request_uuid, "admin").map_err(|e| {
        tracing::error!("hire approve: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(()))
}

pub async fn reject_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(request_uuid): Path<String>,
) -> Result<Json<()>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    hire::reject_request(&state.db_pool, &request_uuid, "admin").map_err(|e| {
        tracing::error!("hire reject: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(()))
}
