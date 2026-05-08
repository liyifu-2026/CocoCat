use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};

use axum::http::HeaderMap;
use crate::auth;
use crate::db::hire::{self, HireRequest, NewHireRequest};
use crate::db::models::NewTask;
use crate::db::tasks;
use crate::dispatch::engine::TaskEvent;

use super::router::AppState;

#[derive(Deserialize)]
pub struct CreateRequest {
    pub requester_agent: String,
    pub new_agent_id: String,
    pub new_agent_name: String,
    pub new_agent_role: String,
    pub reason: String,
}

#[derive(Serialize)]
pub struct HireResponse {
    pub request_uuid: String,
    pub status: String,
}

pub async fn create_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<CreateRequest>,
) -> Result<Json<HireResponse>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let request_uuid = uuid::Uuid::new_v4().to_string();
    let new_req = NewHireRequest {
        request_uuid: request_uuid.clone(),
        requester_agent: req.requester_agent,
        new_agent_id: req.new_agent_id,
        new_agent_name: req.new_agent_name,
        new_agent_role: req.new_agent_role,
        reason: req.reason,
    };
    hire::create_request(&state.db_pool, &new_req).map_err(|e| {
        tracing::error!("hire create: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(HireResponse {
        request_uuid,
        status: "pending".into(),
    }))
}

pub async fn list_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let list = hire::list_pending(&state.db_pool).map_err(|e| {
        tracing::error!("hire list: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({"pending": list})))
}

pub async fn approve_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(request_uuid): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    hire::approve_request(&state.db_pool, &request_uuid, "admin").map_err(|e| {
        tracing::error!("hire approve: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({"status": "approved", "hire_id": request_uuid})))
}

pub async fn reject_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Path(request_uuid): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    hire::reject_request(&state.db_pool, &request_uuid, "admin").map_err(|e| {
        tracing::error!("hire reject: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!({"status": "rejected", "hire_id": request_uuid})))
}

#[derive(Deserialize)]
pub struct PlanRequest {
    pub position: String,
    pub skills: Option<String>,
    pub responsibilities: Option<String>,
    pub traits: Option<String>,
    pub count: Option<i64>,
}

#[derive(Serialize)]
pub struct PlanResponse {
    pub plan_uuid: String,
    pub status: String,
}

pub async fn plan_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<PlanRequest>,
) -> Result<Json<PlanResponse>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let plan_uuid = uuid::Uuid::new_v4().to_string();
    let position = req.position.trim().to_string();
    if position.is_empty() {
        return Err(StatusCode::BAD_REQUEST);
    }

    let skills = req.skills.unwrap_or_default();
    let responsibilities = req.responsibilities.unwrap_or_default();
    let traits = req.traits.unwrap_or_default();
    let count = req.count.unwrap_or(5);

    crate::db::hire::create_plan(
        &state.db_pool,
        &plan_uuid,
        &position,
        &skills,
        &responsibilities,
        &traits,
        count,
    ).map_err(|e| {
        tracing::error!("Failed to create hire plan: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "plan_uuid": plan_uuid,
        "position": position,
        "skills": skills,
        "responsibilities": responsibilities,
        "traits": traits,
        "count": count,
    });

    tasks::create_task(
        &state.db_pool,
        &NewTask {
            task_uuid: task_uuid.clone(),
            target_agent: "leader".to_string(),
            source: "web".into(),
            method: "hire_plan".into(),
            params: params.to_string(),
        },
    ).map_err(|e| {
        tracing::error!("Failed to create hire task: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await.map_err(|e| {
        tracing::error!("Failed to notify dispatch engine: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(PlanResponse {
        plan_uuid,
        status: "generating".to_string(),
    }))
}

#[derive(Serialize)]
pub struct CandidateResponse {
    pub id: String,
    pub name: String,
    pub profile: serde_json::Value,
    pub status: String,
}

pub async fn list_candidates_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let candidates = crate::db::hire::list_pending_candidates(&state.db_pool).map_err(|e| {
        tracing::error!("Failed to list candidates: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let result: Vec<CandidateResponse> = candidates.iter().map(|c| {
        let profile: serde_json::Value = serde_json::from_str(&c.profile).unwrap_or(serde_json::json!({}));
        CandidateResponse {
            id: c.candidate_uuid.clone(),
            name: c.name.clone(),
            profile,
            status: c.status.clone(),
        }
    }).collect();

    Ok(Json(serde_json::json!({"pending": result})))
}

#[derive(Deserialize)]
pub struct CandidateInsertRequest {
    pub candidate_uuid: String,
    pub plan_uuid: String,
    pub name: String,
    pub profile: String,
}

pub async fn insert_candidate_handler(
    State(state): State<AppState>,
    Json(req): Json<CandidateInsertRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    crate::db::hire::insert_candidate(
        &state.db_pool,
        &req.candidate_uuid,
        &req.plan_uuid,
        &req.name,
        &req.profile,
    ).map_err(|e| {
        tracing::error!("Failed to insert candidate: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(serde_json::json!({"status": "inserted"})))
}

#[derive(Deserialize)]
pub struct PlanCompleteRequest {
    pub plan_uuid: String,
    pub status: String,
}

pub async fn plan_complete_handler(
    State(state): State<AppState>,
    Json(req): Json<PlanCompleteRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    crate::db::hire::update_plan_status(
        &state.db_pool,
        &req.plan_uuid,
        &req.status,
    ).map_err(|e| {
        tracing::error!("Failed to update plan status: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(serde_json::json!({"status": "updated"})))
}
