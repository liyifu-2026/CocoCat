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

    let edges = crate::db::tasks::list_transfer_edges(&state.db_pool).map_err(|e| {
        tracing::error!("collab edges: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Collect all node IDs from agents + edge references
    let mut node_ids: std::collections::HashSet<String> = agents.iter().map(|a| a.id.clone()).collect();
    for edge in &edges {
        if let Some(from) = edge.get("from").and_then(|v| v.as_str()) {
            node_ids.insert(from.to_string());
        }
        if let Some(to) = edge.get("to").and_then(|v| v.as_str()) {
            node_ids.insert(to.to_string());
        }
    }

    // Build nodes list
    let mut nodes: Vec<serde_json::Value> = node_ids.iter().map(|id| {
        let label = agents.iter().find(|a| a.id == *id).map(|a| a.name.clone()).unwrap_or_else(|| id.clone());
        serde_json::json!({"id": id, "label": label})
    }).collect();
    nodes.sort_by(|a, b| a["id"].as_str().unwrap_or("").cmp(&b["id"].as_str().unwrap_or("")));

    // Only keep edges referencing valid nodes
    let valid_edges: Vec<serde_json::Value> = edges.into_iter()
        .filter(|e| {
            let from = e.get("from").and_then(|v| v.as_str()).unwrap_or("");
            let to = e.get("to").and_then(|v| v.as_str()).unwrap_or("");
            node_ids.contains(from) && node_ids.contains(to)
        })
        .collect();

    Ok(Json(serde_json::json!({
        "nodes": nodes,
        "edges": valid_edges,
    })))
}
