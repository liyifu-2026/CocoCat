use crate::agent_registry::{self, AgentRegistry};
use cococat::message_bus;
use serde_json::json;
use std::fs;

pub fn process_hire_requests(registry: &mut AgentRegistry) {
    let hire_dir = std::path::Path::new("agents/hire_requests/approved");
    if !hire_dir.exists() {
        return;
    }

    let entries = match fs::read_dir(hire_dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }

        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let hire: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let new_id = hire.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let new_name = hire.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();

        if new_id.is_empty() || new_name.is_empty() {
            continue;
        }

        tracing::info!("Processing hire: {} ({})", new_name, new_id);

        let config_path = "agents/config.toml";
        let mut config_content = fs::read_to_string(config_path).unwrap_or_default();
        let new_entry = format!(
            "\n[[agents]]\nid = \"{}\"\nname = \"{}\"\ninterpreter = \"python\"\nscript = \"py-agent/agent_runtime.py\"\nenabled = true\nscene = \"default\"\n",
            new_id, new_name
        );
        config_content.push_str(&new_entry);
        if let Err(e) = fs::write(config_path, &config_content) {
            tracing::error!("Failed to update config: {e}");
            continue;
        }

        create_agent_dirs(&new_id, &new_name);

        write_profile(&hire, &new_id);

        let new_config = agent_registry::AgentConfig {
            id: new_id.clone(),
            name: new_name.clone(),
            interpreter: "python".to_string(),
            script: "py-agent/agent_runtime.py".to_string(),
            enabled: true,
            scene: Some("default".to_string()),
        };
        registry.configs.push(new_config.clone());
        match registry.start_one(new_config) {
            Ok(()) => tracing::info!("{} ({}) hired and spawned", new_name, new_id),
            Err(e) => tracing::error!("Failed to spawn {}: {}", new_id, e),
        }

        let _ = message_bus::log_message(&message_bus::new_message(
            "system".to_string(),
            "*".to_string(),
            format!("New team member: {} ({})", new_name, new_id),
            "system".to_string(),
        ));

        if let Err(e) = fs::remove_file(&path) {
            tracing::warn!("Failed to remove hire file {}: {e}", path.display());
        }
    }
}

fn create_agent_dirs(id: &str, name: &str) {
    let mem_dir = format!("agents/{}/memory", id);
    if let Err(e) = fs::create_dir_all(&mem_dir) {
        tracing::warn!("Failed to create dir {}: {e}", mem_dir);
    }
    let mem_md = format!("{}/MEMORY.md", mem_dir);
    if let Err(e) = fs::write(&mem_md, format!("# {} Memory\n\nPersonal memories and learnings.\n", name)) {
        tracing::warn!("Failed to write {}: {e}", mem_md);
    }
    let hist = format!("{}/history.jsonl", mem_dir);
    if let Err(e) = fs::write(&hist, "") {
        tracing::warn!("Failed to write {}: {e}", hist);
    }
    let cursor = format!("{}/.dream_cursor", mem_dir);
    if let Err(e) = fs::write(&cursor, "0") {
        tracing::warn!("Failed to write {}: {e}", cursor);
    }
}

fn write_profile(hire: &serde_json::Value, new_id: &str) {
    let profile_path = format!("agents/{}/profile.json", new_id);
    if std::path::Path::new(&profile_path).exists() {
        return;
    }
    if let Some(p) = hire.get("profile") {
        let mut profile = p.clone();
        if profile.get("gender").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
            let gender = if new_id.as_bytes().iter().sum::<u8>() % 2 == 0 { "male" } else { "female" };
            profile["gender"] = serde_json::json!(gender);
        }
        if let Ok(s) = serde_json::to_string_pretty(&profile) {
            if let Err(e) = fs::write(&profile_path, &s) {
                tracing::warn!("Failed to write {}: {e}", profile_path);
            }
        }
    }
}

pub fn process_pending_hires() {
    let pending_dir = std::path::Path::new("agents/hire_requests/pending");
    if !pending_dir.exists() {
        return;
    }

    let entries = match fs::read_dir(pending_dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        if path.file_name().and_then(|n| n.to_str()).map_or(false, |n| n.contains(".processed")) {
            continue;
        }

        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let req: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };

        let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("unknown");
        let id = req.get("id").and_then(|v| v.as_str()).unwrap_or("unknown");
        let role = req.get("profile").and_then(|p| p.get("role")).and_then(|v| v.as_str()).unwrap_or("N/A");
        let scene = req.get("scene").and_then(|v| v.as_str()).unwrap_or("N/A");
        let traits = req.get("profile").and_then(|p| p.get("traits")).and_then(|v| v.as_array()).map(|a| {
            a.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join(", ")
        }).unwrap_or_default();
        let objective = req.get("profile").and_then(|p| p.get("objective")).and_then(|v| v.as_str()).unwrap_or("N/A");

        tracing::info!("--- Pending Hire ---");
        tracing::info!("  Name:      {name}");
        tracing::info!("  ID:        {id}");
        tracing::info!("  Role:      {role}");
        tracing::info!("  Scene:     {scene}");
        tracing::info!("  Traits:    {traits}");
        tracing::info!("  Objective: {objective}");

        let question_path = std::path::Path::new("agents/_ask_user.json");
        let question = json!({
            "question": format!("Process hire request for '{}' ({})", name, id),
            "options": ["Approve", "Modify and Approve", "Reject"],
            "status": "pending"
        });
        let question_str = match serde_json::to_string_pretty(&question) {
            Ok(s) => s,
            Err(e) => {
                tracing::error!("Failed to serialize question: {e}");
                continue;
            }
        };
        if let Err(e) = fs::write(question_path, question_str) {
            tracing::error!("Failed to write question: {e}");
            continue;
        }

        loop {
            std::thread::sleep(std::time::Duration::from_millis(500));
            let answer_content = match fs::read_to_string(question_path) {
                Ok(c) => c,
                Err(_) => continue,
            };
            let answer_json: serde_json::Value = match serde_json::from_str(&answer_content) {
                Ok(v) => v,
                Err(_) => continue,
            };
            if answer_json.get("status").and_then(|v| v.as_str()) == Some("answered") {
                let answer = answer_json.get("answer").and_then(|v| v.as_str()).unwrap_or("").to_string();

                match answer.as_str() {
                    "Approve" | "Modify and Approve" => {
                        let approved_dir = std::path::Path::new("agents/hire_requests/approved");
                        if let Err(e) = fs::create_dir_all(approved_dir) {
                            tracing::warn!("Failed to create approved dir: {e}");
                        }
                        if let Some(fname) = path.file_name() {
                            let dest = approved_dir.join(fname);
                            if let Err(e) = fs::rename(&path, &dest) {
                                tracing::warn!("Failed to move to approved: {e}");
                            }
                            let marker_path = format!("{}.processed", dest.display());
                            if let Err(e) = fs::write(&marker_path, "{}") {
                                tracing::warn!("Failed to write marker {}: {e}", marker_path);
                            }
                            tracing::info!("Approved: {name} ({id})");
                        }
                    }
                    _ => {
                        let rejected_dir = std::path::Path::new("agents/hire_requests/rejected");
                        if let Err(e) = fs::create_dir_all(rejected_dir) {
                            tracing::warn!("Failed to create rejected dir: {e}");
                        }
                        if let Some(fname) = path.file_name() {
                            let dest = rejected_dir.join(fname);
                            if let Err(e) = fs::rename(&path, &dest) {
                                tracing::warn!("Failed to move to rejected: {e}");
                            }
                            let marker_path = format!("{}.processed", dest.display());
                            if let Err(e) = fs::write(&marker_path, "{}") {
                                tracing::warn!("Failed to write marker {}: {e}", marker_path);
                            }
                            tracing::info!("Rejected: {name} ({id})");
                        }
                    }
                }

                if let Err(e) = fs::remove_file(question_path) {
                    tracing::warn!("Failed to remove question file: {e}");
                }
                break;
            }
        }
    }
}
