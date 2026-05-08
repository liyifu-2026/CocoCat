use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;

use crate::auth;
use crate::db::models::NewTask;
use crate::db::tasks;
use crate::dispatch::engine::TaskEvent;

use super::router::AppState;

#[derive(Deserialize)]
pub struct CreateTaskRequest {
    task: String,
    assigned_to: String,
    task_type: Option<String>,     // "one_time" (default) | "recurring_template"
    recurrence: Option<i64>,       // interval in minutes, required if recurring
}

#[derive(Deserialize)]
pub struct UpdateTaskRequest {
    status: Option<String>,
    result: Option<String>,
}

pub async fn list_schedule_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let tasks = tasks::list_all_tasks(&state.db_pool).map_err(|e| {
        tracing::error!("schedule list: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "tasks": tasks })))
}

pub async fn create_schedule_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<CreateTaskRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let is_recurring = req.task_type.as_deref() == Some("recurring_template");
    let task_type = if is_recurring { "recurring_template" } else { "one_time" };
    let recurrence = req.recurrence.map(|m| serde_json::json!({"interval": m}).to_string());

    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({ "task": req.task }).to_string();

    let new_task = NewTask {
        task_uuid,
        target_agent: req.assigned_to,
        source: "user".into(),
        method: "schedule".into(),
        params,
        task_type: Some(task_type.into()),
        recurrence,
        ..Default::default()
    };
    let task = tasks::create_task(&state.db_pool, &new_task).map_err(|e| {
        tracing::error!("schedule create: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Notify dispatch engine only for one_time tasks
    if !is_recurring {
        if state.task_tx.send(TaskEvent::NewTask {
            task_uuid: task.task_uuid.clone(),
        }).await.is_err() {
            tracing::warn!("Dispatch engine not listening, task will not be processed");
        }
    }

    let agent_name = crate::db::agents::get_agent(&state.db_pool, &task.target_agent)
        .ok()
        .flatten()
        .map(|a| a.name)
        .unwrap_or_else(|| task.target_agent.clone());

    Ok(Json(serde_json::json!({
        "task": {
            "id": task.id,
            "task": req.task,
            "assigned_to": agent_name,
            "status": task.status,
            "task_type": task.task_type,
            "recurrence": task.recurrence,
            "created_at": task.created_at,
            "result": task.result,
        }
    })))
}

pub async fn update_schedule_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(id): Path<i64>,
    Json(req): Json<UpdateTaskRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    if let Some(status) = &req.status {
        tasks::update_task_status(&state.db_pool, id, status, req.result.as_deref())
            .map_err(|e| {
                tracing::error!("schedule update: {}", e);
                StatusCode::INTERNAL_SERVER_ERROR
            })?;
    }
    let task = tasks::get_task_by_id(&state.db_pool, id)
        .map_err(|e| {
            tracing::error!("schedule get: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .ok_or(StatusCode::NOT_FOUND)?;
    let agent_name = crate::db::agents::get_agent(&state.db_pool, &task.target_agent)
        .ok()
        .flatten()
        .map(|a| a.name)
        .unwrap_or_else(|| task.target_agent.clone());
    let task_desc = serde_json::from_str::<serde_json::Value>(&task.params)
        .ok()
        .and_then(|p| p.get("task").and_then(|v| v.as_str().map(String::from)))
        .unwrap_or_default();
    Ok(Json(serde_json::json!({
        "task": {
            "id": task.id,
            "task": task_desc,
            "assigned_to": agent_name,
            "status": task.status,
            "created_at": task.created_at,
            "result": task.result,
        }
    })))
}

pub async fn delete_schedule_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(id): Path<i64>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    tasks::delete_task_by_id(&state.db_pool, id).map_err(|e| {
        tracing::error!("schedule delete: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({ "status": "deleted" })))
}
