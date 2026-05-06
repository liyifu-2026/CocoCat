use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

use crate::auth;
use crate::db::pool::DbPool;

use super::router::AppState;

fn agent_mem_dir(agent_id: &str) -> PathBuf {
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.push("agents");
    p.push(agent_id);
    p.push("memory");
    p
}

fn read_file_or_default(path: &PathBuf) -> String {
    if path.exists() {
        std::fs::read_to_string(path).unwrap_or_default()
    } else {
        String::new()
    }
}

fn read_jsonl(path: &PathBuf, limit: usize) -> Vec<serde_json::Value> {
    if !path.exists() {
        return vec![];
    }
    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return vec![],
    };
    let mut entries: Vec<serde_json::Value> = content
        .lines()
        .filter_map(|line| serde_json::from_str(line).ok())
        .collect();
    entries.reverse();
    entries.truncate(limit);
    entries
}

fn get_agent_metadata(pool: &DbPool, agent_id: &str) -> Result<serde_json::Value, StatusCode> {
    let conn = pool.get().map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let meta: String = conn
        .query_row(
            "SELECT metadata FROM agents WHERE id = ?1",
            rusqlite::params![agent_id],
            |row| row.get(0),
        )
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(serde_json::from_str::<serde_json::Value>(&meta)
        .unwrap_or(serde_json::Value::Object(serde_json::Map::new())))
}

fn update_agent_metadata(
    pool: &DbPool,
    agent_id: &str,
    upd: impl Fn(&mut serde_json::Value),
) -> Result<serde_json::Value, StatusCode> {
    let mut meta = get_agent_metadata(pool, agent_id)?;
    upd(&mut meta);
    let meta_str = serde_json::to_string(&meta).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let conn = pool.get().map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    conn.execute(
        "UPDATE agents SET metadata = ?1 WHERE id = ?2",
        rusqlite::params![meta_str, agent_id],
    )
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(meta)
}

// --- Profile ---

#[derive(Serialize, Deserialize)]
pub struct AgentProfile {
    pub objective: String,
    pub traits: Vec<String>,
    pub background: String,
    pub rules: Vec<String>,
}

impl Default for AgentProfile {
    fn default() -> Self {
        Self {
            objective: String::new(),
            traits: vec![],
            background: String::new(),
            rules: vec![],
        }
    }
}

pub async fn get_profile_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<AgentProfile>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let meta = get_agent_metadata(&state.db_pool, &agent_id)?;
    let profile = meta
        .get("profile")
        .and_then(|p| serde_json::from_value(p.clone()).ok())
        .unwrap_or_default();
    Ok(Json(profile))
}

// --- Skills ---

#[derive(Serialize, Deserialize)]
pub struct AgentSkillsResponse {
    pub public: Vec<String>,
    pub private: Vec<String>,
}

pub async fn get_skills_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<AgentSkillsResponse>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let conn = state.db_pool.get().map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let mut stmt = conn
        .prepare("SELECT name, scope FROM skills WHERE agent_id = ?1")
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let rows = stmt
        .query_map(rusqlite::params![agent_id], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let mut public = vec![];
    let mut private = vec![];
    for row in rows {
        if let Ok((name, scope)) = row {
            match scope.as_str() {
                "private" => private.push(name),
                _ => public.push(name),
            }
        }
    }
    Ok(Json(AgentSkillsResponse { public, private }))
}

#[derive(Deserialize)]
pub struct UpdateSkillsRequest {
    pub public: Vec<String>,
    pub private: Vec<String>,
}

pub async fn update_skills_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
    Json(req): Json<UpdateSkillsRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let conn = state.db_pool.get().map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    conn.execute("DELETE FROM skills WHERE agent_id = ?1", rusqlite::params![agent_id])
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    for name in &req.public {
        conn.execute(
            "INSERT INTO skills (id, name, scope, content, agent_id) VALUES (?1, ?2, 'public', '', ?3)",
            rusqlite::params![format!("{agent_id}/{name}"), name, agent_id],
        )
        .ok();
    }
    for name in &req.private {
        conn.execute(
            "INSERT INTO skills (id, name, scope, content, agent_id) VALUES (?1, ?2, 'private', '', ?3)",
            rusqlite::params![format!("{agent_id}/{name}"), name, agent_id],
        )
        .ok();
    }
    Ok(Json(serde_json::json!({"status": "ok"})))
}

// --- Memory ---

pub async fn get_memory_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let path = agent_mem_dir(&agent_id).join("MEMORY.md");
    let content = read_file_or_default(&path);
    Ok(Json(serde_json::json!({ "content": content })))
}

// --- History ---

#[derive(Deserialize)]
pub struct HistoryQuery {
    limit: Option<usize>,
}

pub async fn get_history_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
    axum::extract::Query(query): axum::extract::Query<HistoryQuery>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let limit = query.limit.unwrap_or(50).min(500);
    let path = agent_mem_dir(&agent_id).join("history.jsonl");
    let entries = read_jsonl(&path, limit);
    Ok(Json(serde_json::json!({ "entries": entries })))
}

// --- Display ---

#[derive(Serialize, Deserialize, Clone)]
pub struct AgentDisplay {
    pub nickname: String,
    pub avatar: String,
    pub color: String,
    #[serde(default)]
    pub gender: String,
}

impl Default for AgentDisplay {
    fn default() -> Self {
        Self {
            nickname: String::new(),
            avatar: String::new(),
            color: String::new(),
            gender: String::new(),
        }
    }
}

pub async fn list_displays_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let agents = crate::db::agents::load_agents(&state.db_pool)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut result = serde_json::Map::new();
    for agent in &agents {
        let meta: serde_json::Value =
            serde_json::from_str(&agent.metadata).unwrap_or(serde_json::json!({}));
        let display = meta
            .get("display")
            .and_then(|d| serde_json::from_value(d.clone()).ok())
            .unwrap_or_else(|| AgentDisplay {
                nickname: agent.name.clone(),
                ..Default::default()
            });
        result.insert(agent.id.clone(), serde_json::to_value(display).unwrap_or_default());
    }

    Ok(Json(serde_json::Value::Object(result)))
}

pub async fn get_display_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
) -> Result<Json<AgentDisplay>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let meta = get_agent_metadata(&state.db_pool, &agent_id)?;
    let display = meta
        .get("display")
        .and_then(|d| serde_json::from_value(d.clone()).ok())
        .unwrap_or_default();
    Ok(Json(display))
}

pub async fn update_display_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(agent_id): Path<String>,
    Json(req): Json<AgentDisplay>,
) -> Result<Json<AgentDisplay>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let display = req.clone();
    update_agent_metadata(&state.db_pool, &agent_id, |meta| {
        meta["display"] = serde_json::to_value(display.clone()).unwrap_or_default();
    })?;
    Ok(Json(req))
}
