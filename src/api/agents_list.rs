use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use serde::{Deserialize, Serialize};

use crate::auth;
use super::router::AppState;

#[derive(Serialize)]
pub struct AgentResponse {
    pub id: String,
    pub name: String,
    pub role: String,
    pub model: String,
    pub scene_id: String,
    pub status: String,
    pub system_prompt: String,
    pub created_at: String,
    pub last_heartbeat_at: Option<String>,
}

fn agent_to_response(a: &crate::db::models::Agent) -> AgentResponse {
    AgentResponse {
        id: a.id.clone(),
        name: a.name.clone(),
        role: a.role.clone(),
        model: a.model.clone(),
        scene_id: a.scene_id.clone(),
        status: a.status.clone(),
        system_prompt: a.system_prompt.clone(),
        created_at: a.created_at.clone(),
        last_heartbeat_at: a.last_heartbeat_at.clone(),
    }
}

#[derive(Deserialize)]
pub struct UpdateAgentRequest {
    pub name: Option<String>,
    pub system_prompt: Option<String>,
    pub scene_id: Option<String>,
}

pub async fn list_agents(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<AgentResponse>>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let agents = crate::db::agents::load_agents(&state.db_pool)
        .map_err(|e| {
            tracing::error!("list_agents: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(agents.iter().map(agent_to_response).collect()))
}

pub async fn get_agent(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    match crate::db::agents::get_agent(&state.db_pool, &agent_id)
        .map_err(|e| {
            tracing::error!("get_agent: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })? {
        Some(a) => Ok(Json(serde_json::to_value(agent_to_response(&a)).unwrap())),
        None => Ok(Json(serde_json::json!({"error": "not found"}))),
    }
}

pub async fn update_agent(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
    Json(req): Json<UpdateAgentRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let conn = state.db_pool.get().map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if let Some(ref name) = req.name {
        conn.execute("UPDATE agents SET name = ?1 WHERE id = ?2", rusqlite::params![name, agent_id])
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    }
    if let Some(ref sp) = req.system_prompt {
        conn.execute("UPDATE agents SET system_prompt = ?1 WHERE id = ?2", rusqlite::params![sp, agent_id])
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    }
    if let Some(ref sid) = req.scene_id {
        conn.execute("UPDATE agents SET scene_id = ?1 WHERE id = ?2", rusqlite::params![sid, agent_id])
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    }
    drop(conn);
    match crate::db::agents::get_agent(&state.db_pool, &agent_id)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)? {
        Some(a) => Ok(Json(serde_json::to_value(agent_to_response(&a)).unwrap())),
        None => Ok(Json(serde_json::json!({"error": "not found"}))),
    }
}

pub async fn delete_agent(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    crate::db::agents::update_status(&state.db_pool, &agent_id, "stopped")
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "stopped"})))
}
