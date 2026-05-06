use axum::{
    extract::State,
    http::StatusCode,
    Json,
};

use crate::auth;

use super::router::AppState;

pub async fn get_collab_graph_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let agents = crate::db::agents::load_agents(&state.db_pool).map_err(|e| {
        tracing::error!("collab agents: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let nodes: Vec<serde_json::Value> = agents
        .iter()
        .map(|a| {
            serde_json::json!({
                "id": a.id,
                "label": a.name,
            })
        })
        .collect();

    let edges = crate::db::tasks::list_transfer_edges(&state.db_pool).map_err(|e| {
        tracing::error!("collab edges: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(serde_json::json!({
        "nodes": nodes,
        "edges": edges,
    })))
}
