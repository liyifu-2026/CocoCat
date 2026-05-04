use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};

use crate::auth;
use crate::db::tasks;

use super::router::AppState;

pub async fn get_task_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(task_uuid): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    tasks::get_task_by_uuid(&state.db_pool, &task_uuid)
        .map_err(|e| {
            tracing::error!("task get: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .ok_or(StatusCode::NOT_FOUND)
        .map(|t| {
            Json(serde_json::json!({
                "task_uuid": t.task_uuid,
                "status": t.status,
                "result": t.result,
                "error": t.error,
            }))
        })
}
