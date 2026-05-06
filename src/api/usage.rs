use axum::{
    extract::{Query, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;

use crate::auth;

use super::router::AppState;

#[derive(Deserialize)]
pub struct UsageQuery {
    limit: Option<usize>,
}

pub async fn get_usage_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Query(query): Query<UsageQuery>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let limit = query.limit.unwrap_or(100).min(1000);
    let usage = crate::db::usage::read_usage(limit);
    Ok(Json(serde_json::json!({ "usage": usage })))
}
