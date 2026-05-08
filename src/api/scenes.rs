use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;

use crate::auth;
use crate::db::scenes::{self, Scene};

use super::router::AppState;

#[derive(Deserialize)]
pub struct CreateSceneRequest {
    pub id: String,
    pub name: String,
    pub description: Option<String>,
    pub roster: Option<Vec<String>>,
}

pub async fn list_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let list = scenes::list_scenes(&state.db_pool).map_err(|e| {
        tracing::error!("scenes list: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({"scenes": list})))
}

pub async fn get_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(id): Path<String>,
) -> Result<Json<Scene>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    scenes::get_scene(&state.db_pool, &id)
        .map_err(|e| {
            tracing::error!("scenes get: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .ok_or(StatusCode::NOT_FOUND)
        .map(Json)
}

pub async fn create_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<CreateSceneRequest>,
) -> Result<Json<Scene>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let roster = serde_json::to_string(&req.roster.unwrap_or_default()).unwrap_or_default();
    scenes::create_scene(
        &state.db_pool,
        &req.id,
        &req.name,
        &req.description.unwrap_or_default(),
        &roster,
    ).map_err(|e| {
        tracing::error!("scenes create: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })
    .map(Json)
}

pub async fn delete_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(id): Path<String>,
) -> Result<Json<()>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    scenes::delete_scene(&state.db_pool, &id).map_err(|e| {
        tracing::error!("scenes delete: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(()))
}
