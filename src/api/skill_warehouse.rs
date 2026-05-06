use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use serde::Deserialize;

use crate::auth;
use crate::db::skill_warehouse;

use super::router::AppState;

#[derive(Deserialize)]
pub struct InstallRequest {
    pub id: String,
    pub name: String,
    pub description: Option<String>,
    pub content: Option<String>,
    pub source: Option<String>,
    pub source_url: Option<String>,
    pub author: Option<String>,
    pub tags: Option<String>,
}

#[derive(Deserialize)]
pub struct AssignSkillsRequest {
    pub skill_ids: Vec<String>,
}

pub async fn list_warehouse_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let skills = skill_warehouse::list_warehouse(&state.db_pool).map_err(|e| {
        tracing::error!("warehouse list: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "skills": skills })))
}

pub async fn install_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<InstallRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let skill = skill_warehouse::upsert_warehouse_skill(
        &state.db_pool,
        &req.id, &req.name,
        &req.description.unwrap_or_default(),
        &req.content.unwrap_or_default(),
        &req.source.unwrap_or_else(|| "manual".into()),
        req.source_url.as_deref(),
        &req.author.unwrap_or_else(|| "admin".into()),
        &req.tags.unwrap_or_else(|| "[]".into()),
        "{}",
    ).map_err(|e| {
        tracing::error!("warehouse install: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "skill": skill })))
}

pub async fn delete_warehouse_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    skill_warehouse::delete_warehouse_skill(&state.db_pool, &id).map_err(|e| {
        tracing::error!("warehouse delete: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "status": "deleted" })))
}

pub async fn get_agent_skills_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let skills = skill_warehouse::get_agent_skills(&state.db_pool, &agent_id).map_err(|e| {
        tracing::error!("agent skills list: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "skills": skills })))
}

pub async fn assign_skills_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
    Json(req): Json<AssignSkillsRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    skill_warehouse::set_agent_skills(&state.db_pool, &agent_id, &req.skill_ids).map_err(|e| {
        tracing::error!("agent skills assign: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "status": "assigned" })))
}

pub async fn capabilities_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let caps = skill_warehouse::capabilities(&state.db_pool).map_err(|e| {
        tracing::error!("capabilities: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "agents": caps })))
}
