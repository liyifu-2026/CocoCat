use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use serde::Deserialize;
use std::path::PathBuf;

use crate::auth;
use crate::db::tasks;
use crate::db::models::NewTask;
use crate::dispatch::engine::TaskEvent;

use super::router::AppState;

#[derive(Deserialize)]
pub struct ProcessRequest {
    pub kb_name: String,
    pub filename: String,
}

pub async fn upload_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<ProcessRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let kb_path = PathBuf::from("knowledge").join(&req.kb_name);

    // Create KB directory structure if new
    if !kb_path.exists() {
        std::fs::create_dir_all(kb_path.join("raw/sources"))
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        std::fs::create_dir_all(kb_path.join("wiki/entities"))
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        std::fs::create_dir_all(kb_path.join("wiki/concepts"))
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        // Copy schema template
        let template = std::path::Path::new("skills/public/knowledge-ingestion.md");
        if template.exists() {
            let _ = std::fs::copy(template, kb_path.join("schema.md"));
        }

        // Create empty index and log
        let _ = std::fs::write(kb_path.join("index.md"), "# Index\n\n");
        let _ = std::fs::write(kb_path.join("log.md"), "# Log\n\n");
    }

    let file_path = kb_path.join("raw/sources").join(&req.filename);

    // Write file
    std::fs::write(&file_path, &req.filename)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Extract text from uploaded file (PDF, DOCX, HTML, etc.)
    let extracted_path = kb_path.join("raw/sources").join(format!("{}.md", req.filename));
    if let Ok(output) = std::process::Command::new("python3")
        .arg("tools/extract_text.py")
        .arg(&file_path)
        .output()
    {
        if output.status.success() {
            if let Ok(json_str) = String::from_utf8(output.stdout) {
                if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&json_str) {
                    if let Some(text) = parsed.get("text").and_then(|v| v.as_str()) {
                        let meta = format!(
                            "---\nfilename: {}\n---\n\n",
                            req.filename
                        );
                        let _ = std::fs::write(&extracted_path, format!("{}{}", meta, text));
                    }
                }
            }
        }
    }

    // Create task for Leader
    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "kb_name": req.kb_name,
        "filename": req.filename,
        "source_path": file_path.to_string_lossy().to_string(),
        "extracted_path": extracted_path.to_string_lossy().to_string(),
    });

    tasks::create_task(
        &state.db_pool,
        &NewTask {
            task_uuid: task_uuid.clone(),
            target_agent: "leader".into(),
            source: "kb".into(),
            method: "process_kb_source".into(),
            params: params.to_string(),
        },
    ).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await;

    Ok(Json(serde_json::json!({
        "status": "queued",
        "task_uuid": task_uuid,
        "kb_name": req.kb_name,
    })))
}

pub async fn process_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(kb_name): Path<String>,
    Json(req): Json<serde_json::Value>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let filename = req.get("filename")
        .and_then(|v| v.as_str())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let task_uuid = uuid::Uuid::new_v4().to_string();
    let params = serde_json::json!({
        "kb_name": kb_name,
        "filename": filename,
    });

    tasks::create_task(
        &state.db_pool,
        &NewTask {
            task_uuid: task_uuid.clone(),
            target_agent: "leader".into(),
            source: "kb".into(),
            method: "process_kb_source".into(),
            params: params.to_string(),
        },
    ).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = state.task_tx.send(TaskEvent::NewTask {
        task_uuid: task_uuid.clone(),
    }).await;

    Ok(Json(serde_json::json!({
        "status": "queued",
        "task_uuid": task_uuid,
    })))
}

pub async fn tasks_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(kb_name): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let all_tasks = tasks::list_all_tasks(&state.db_pool)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Filter tasks related to this KB
    let kb_tasks: Vec<_> = all_tasks.into_iter()
        .filter(|t| t["params"].as_str().map_or(false, |p| p.contains(&kb_name)))
        .collect();

    Ok(Json(serde_json::json!({ "tasks": kb_tasks })))
}

#[derive(Deserialize)]
pub struct ExtractRequest {
    pub filename: String,
    pub content: String,
}

pub async fn extract_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<ExtractRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;

    let tmp_dir = std::env::temp_dir().join("cococat_uploads");
    let _ = std::fs::create_dir_all(&tmp_dir);
    let tmp_path = tmp_dir.join(&req.filename);
    let _ = std::fs::write(&tmp_path, &req.content);

    let result = std::process::Command::new("python3")
        .arg("tools/extract_text.py")
        .arg(&tmp_path)
        .output();

    let _ = std::fs::remove_file(&tmp_path);

    match result {
        Ok(output) if output.status.success() => {
            let json_str = String::from_utf8_lossy(&output.stdout);
            if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&json_str) {
                let text = parsed.get("text").and_then(|v| v.as_str()).unwrap_or("");
                return Ok(Json(serde_json::json!({
                    "filename": req.filename, "text": text, "pages": parsed.get("pages"),
                })));
            }
            Ok(Json(serde_json::json!({"filename": req.filename, "text": json_str})))
        }
        _ => Ok(Json(serde_json::json!({"filename": req.filename, "text": req.content}))),
    }
}
