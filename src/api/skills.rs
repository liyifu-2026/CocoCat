use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;

use crate::auth;
use crate::db::skills::{self, Skill};

use super::router::AppState;

#[derive(Deserialize)]
pub struct CreateSkillRequest {
    pub id: String,
    pub name: String,
    pub scope: String,
    pub content: String,
}

pub async fn list_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> Result<Json<Vec<Skill>>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let scope = params.get("scope").map(|s| s.as_str());
    skills::list_skills(&state.db_pool, scope).map_err(|e| {
        tracing::error!("skills list: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    }).map(Json)
}

pub async fn get_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(id): Path<String>,
) -> Result<Json<Skill>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    skills::get_skill(&state.db_pool, &id)
        .map_err(|e| {
            tracing::error!("skills get: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .ok_or(StatusCode::NOT_FOUND)
        .map(Json)
}

pub async fn create_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<CreateSkillRequest>,
) -> Result<Json<Skill>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    skills::create_skill(&state.db_pool, &req.id, &req.name, &req.scope, &req.content)
        .map_err(|e| {
            tracing::error!("skills create: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })
        .map(Json)
}
