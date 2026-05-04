use crate::agent_registry::AgentRegistry;
use cococat::message_bus;
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT_TASK_ID: AtomicU64 = AtomicU64::new(1);

pub fn check_and_process_dispatches(registry: &mut AgentRegistry) {
    let dispatch_dir = std::path::Path::new("agents/dispatch_queue");
    if !dispatch_dir.exists() {
        return;
    }

    let entries = match std::fs::read_dir(dispatch_dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    let mut processed = Vec::new();

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }

        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let dispatch: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let target_id = dispatch.get("target_id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let method = dispatch.get("method").and_then(|v| v.as_str()).unwrap_or("task").to_string();
        let params = dispatch.get("params").cloned();
        let prompt = params.as_ref()
            .and_then(|p| p.get("prompt"))
            .and_then(|p| p.as_str())
            .unwrap_or("")
            .to_string();

        if target_id.is_empty() {
            continue;
        }

        let task_id = NEXT_TASK_ID.fetch_add(1, Ordering::Relaxed);

        message_bus::log_message(&message_bus::ChatMessage {
            task_id: Some(task_id),
            ..message_bus::new_message(
                "leader".to_string(),
                target_id.clone(),
                format!("Dispatching task: {:.80}", prompt),
                "task".to_string(),
            )
        }).ok();

        tracing::info!("Routing dispatch to '{}'...", target_id);
        match registry.dispatch_message(&target_id, &method, params) {
            Ok(response) => {
                tracing::info!("Dispatch to '{}' succeeded", target_id);
                if let Some(ref result) = response.result {
                    if let Some(content) = result["content"].as_str() {
                        tracing::info!("Response: {:.120}", content);
                        message_bus::log_message(&message_bus::ChatMessage {
                            task_id: Some(task_id),
                            ..message_bus::new_message(
                                target_id.clone(),
                                "leader".to_string(),
                                content.to_string(),
                                "reply".to_string(),
                            )
                        }).ok();
                    }
                } else if let Some(ref err) = response.error {
                    tracing::error!("Dispatch error [{}]: {}", err.code, err.message);
                    message_bus::log_message(&message_bus::ChatMessage {
                        task_id: Some(task_id),
                        ..message_bus::new_message(
                            target_id.clone(),
                            "leader".to_string(),
                            format!("Error [{}]: {}", err.code, err.message),
                            "reply".to_string(),
                        )
                    }).ok();
                }
            }
            Err(e) => {
                tracing::error!("Dispatch to '{}' failed: {}", target_id, e);
                message_bus::log_message(&message_bus::ChatMessage {
                    task_id: Some(task_id),
                    ..message_bus::new_message(
                        "system".to_string(),
                        "leader".to_string(),
                        format!("Dispatch to {} failed: {}", target_id, e),
                        "system".to_string(),
                    )
                }).ok();
            }
        }

        processed.push(path);
    }

    for path in processed {
        if let Err(e) = std::fs::remove_file(&path) {
            tracing::warn!("Failed to remove dispatch file {}: {e}", path.display());
        }
    }
}
