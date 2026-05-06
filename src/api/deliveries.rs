use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode, header},
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use crate::auth;
use crate::db::deliveries as db_del;
use super::router::AppState;

#[derive(Deserialize)]
pub struct CreateDeliveryRequest {
    pub id: String,
    pub subject: String,
    pub from_agent: String,
    pub body: String,
    pub files_json: String,
}

pub async fn create_delivery(
    State(state): State<AppState>,
    Json(req): Json<CreateDeliveryRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    db_del::create_delivery(&state.db_pool, &req.id, &req.subject, &req.from_agent, &req.body, &req.files_json)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "created"})))
}

pub async fn list_deliveries(
    State(state): State<AppState>, headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let deliveries = db_del::list_deliveries(&state.db_pool)
        .map_err(|e| { tracing::error!("list_deliveries: {}", e); StatusCode::INTERNAL_SERVER_ERROR })?;
    Ok(Json(serde_json::json!({"deliveries": deliveries})))
}

pub async fn get_delivery(
    State(state): State<AppState>, headers: HeaderMap, Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    match db_del::get_delivery(&state.db_pool, &id)
        .map_err(|e| { tracing::error!("get_delivery: {}", e); StatusCode::INTERNAL_SERVER_ERROR })? {
        Some(d) => Ok(Json(serde_json::to_value(d).unwrap())),
        None => Ok(Json(serde_json::json!({"error": "not found"}))),
    }
}

pub async fn archive_delivery(
    State(state): State<AppState>, headers: HeaderMap, Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_del::update_status(&state.db_pool, &id, "archived").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "archived"})))
}

pub async fn mark_read(
    State(state): State<AppState>, headers: HeaderMap, Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_del::update_status(&state.db_pool, &id, "read").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "read"})))
}

pub async fn approve_delivery(
    State(state): State<AppState>, headers: HeaderMap, Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_del::update_status(&state.db_pool, &id, "approved").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "approved"})))
}

pub async fn request_changes(
    State(state): State<AppState>, headers: HeaderMap, Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_del::update_status(&state.db_pool, &id, "changes_requested").map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "changes_requested"})))
}

pub async fn download_file(
    State(state): State<AppState>, headers: HeaderMap, Path((id, filename)): Path<(String, String)>,
) -> Result<axum::response::Response, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let base = std::env::current_dir().map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?.join("data").join("deliveries").join(&id);
    let file_path = base.join(&filename);
    if !file_path.exists() {
        return Ok(Json(serde_json::json!({"error": "file not found"})).into_response());
    }
    let data = tokio::fs::read(&file_path).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let mime = mime_guess::from_path(&filename).first_or_octet_stream();
    Ok(([(header::CONTENT_TYPE, mime.as_ref())], data).into_response())
}
