use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use serde::Deserialize;

use crate::auth;
use crate::db::chat_groups::{self as db_chat, ChatGroupMember, ChatMessage};
use crate::db::tasks;
use crate::db::models::NewTask;
use crate::dispatch::engine::TaskEvent;

use super::router::AppState;

#[derive(Deserialize)]
pub struct CreateGroupRequest {
    pub name: String,
    pub members: Vec<MemberEntry>,
    pub announcement: Option<String>,
}

#[derive(Deserialize)]
pub struct MemberEntry {
    pub id: String,
    pub name: String,
    pub role: Option<String>,
}

#[derive(Deserialize)]
pub struct SendMessageRequest {
    pub content: String,
    pub from: Option<String>,
}

#[derive(Deserialize)]
pub struct UpdateGroupRequest {
    pub name: Option<String>,
    pub announcement: Option<String>,
}

#[derive(Deserialize)]
pub struct AddMemberRequest {
    pub agent_id: String,
    pub name: String,
}

#[derive(Deserialize)]
pub struct MarkReadRequest {
    pub agent_id: String,
    pub score: Option<i64>,
}

#[derive(Deserialize)]
pub struct MessagesQuery {
    pub limit: Option<i64>,
}

pub async fn list_groups(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let groups = db_chat::list_groups(&state.db_pool).map_err(|e| {
        tracing::error!("list_groups: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({"groups": groups})))
}

pub async fn create_group(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<CreateGroupRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let group_id = req.name.to_lowercase().replace(' ', "-");
    let members: Vec<ChatGroupMember> = req.members.into_iter().map(|m| ChatGroupMember {
        agent_id: m.id,
        name: m.name,
        role: m.role.unwrap_or_else(|| "member".to_string()),
    }).collect();

    let group = db_chat::create_group(
        &state.db_pool,
        &group_id,
        &req.name,
        req.announcement.as_deref().unwrap_or(""),
        &members,
    ).map_err(|e| {
        tracing::error!("create_group: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(serde_json::json!({"status": "created", "group": group})))
}

pub async fn get_group(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    match db_chat::get_group(&state.db_pool, &group_id).map_err(|e| {
        tracing::error!("get_group: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })? {
        Some(group) => Ok(Json(serde_json::json!(group))),
        None => Ok(Json(serde_json::json!({"error": "group not found"}))),
    }
}

pub async fn update_group(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
    Json(req): Json<UpdateGroupRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::update_group(&state.db_pool, &group_id, req.name.as_deref(), req.announcement.as_deref())
        .map_err(|e| {
            tracing::error!("update_group: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "updated"})))
}

pub async fn delete_group(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::delete_group(&state.db_pool, &group_id).map_err(|e| {
        tracing::error!("delete_group: {}", e);
        StatusCode::BAD_REQUEST
    })?;
    Ok(Json(serde_json::json!({"status": "deleted"})))
}

pub async fn add_member(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
    Json(req): Json<AddMemberRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::add_member(&state.db_pool, &group_id, &req.agent_id, &req.name, "member")
        .map_err(|e| {
            tracing::error!("add_member: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "added"})))
}

pub async fn remove_member(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((group_id, agent_id)): Path<(String, String)>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    if agent_id == "admin" {
        return Ok(Json(serde_json::json!({"error": "cannot remove admin"})));
    }
    db_chat::remove_member(&state.db_pool, &group_id, &agent_id)
        .map_err(|e| {
            tracing::error!("remove_member: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "removed"})))
}

pub async fn send_message(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
    Json(req): Json<SendMessageRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let content = req.content.trim().to_string();
    if content.is_empty() {
        return Ok(Json(serde_json::json!({"error": "content is required"})));
    }
    let from = req.from.unwrap_or_else(|| "admin".to_string());

    // Get group to find members
    let group = db_chat::get_group(&state.db_pool, &group_id)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    // Insert user message
    let msg_id = db_chat::send_message(&state.db_pool, &group_id, &content, &from)
        .map_err(|e| {
            tracing::error!("send_message: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Determine which agents to dispatch to
    let target_agents: Vec<String> = if group_id.starts_with("dm_") {
        // DM mode: dispatch to the DM's agent directly
        let agent_id = group_id.strip_prefix("dm_").unwrap_or("").to_string();
        if agent_id.is_empty() {
            return Ok(Json(serde_json::json!({"error": "invalid dm group"})));
        }
        vec![agent_id]
    } else {
        let mentions = db_chat::parse_mentions(&content);
        if mentions.is_empty() {
            group.members.iter()
                .filter(|m| m.agent_id != "admin")
                .map(|m| m.agent_id.clone())
                .collect()
        } else {
            mentions
        }
    };

    // Create task for each target agent
    for agent_id in &target_agents {
        let task_uuid = uuid::Uuid::new_v4().to_string();
        let params = serde_json::json!({
            "content": content,
            "chat_group": group_id,
            "source_msg_id": msg_id,
            "scene_id": "default",
        });

        if let Err(e) = tasks::create_task(
            &state.db_pool,
            &NewTask {
                task_uuid: task_uuid.clone(),
                target_agent: agent_id.clone(),
                source: "chat".into(),
                method: "chat".into(),
                params: params.to_string(),
            },
        ) {
            tracing::error!("create_task for {}: {}", agent_id, e);
            continue;
        }

        let _ = state.task_tx.send(TaskEvent::NewTask {
            task_uuid: task_uuid.clone(),
        }).await;
    }

    // Return the newly created message
    let messages = db_chat::get_messages(&state.db_pool, &group_id, 1).unwrap_or_default();
    let message = messages.last().cloned().unwrap_or(ChatMessage {
        id: msg_id,
        from: from.clone(),
        content: content.clone(),
        timestamp: chrono::Utc::now().to_rfc3339(),
        recalled: false,
        mentions: Default::default(),
        read_by: Default::default(),
    });

    Ok(Json(serde_json::json!({"status": "sent", "message": message})))
}

pub async fn get_messages(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(group_id): Path<String>,
    Query(query): Query<MessagesQuery>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let limit = query.limit.unwrap_or(100);
    let messages = db_chat::get_messages(&state.db_pool, &group_id, limit)
        .map_err(|e| {
            tracing::error!("get_messages: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"messages": messages})))
}

pub async fn recall_message(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((_group_id, msg_id)): Path<(String, i64)>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::recall_message(&state.db_pool, msg_id)
        .map_err(|e| {
            tracing::error!("recall_message: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "recalled"})))
}

pub async fn mark_read(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((_group_id, msg_id)): Path<(String, i64)>,
    Json(req): Json<MarkReadRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_chat::mark_read(&state.db_pool, msg_id, &req.agent_id, req.score.unwrap_or(0))
        .map_err(|e| {
            tracing::error!("mark_read: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    Ok(Json(serde_json::json!({"status": "read"})))
}
