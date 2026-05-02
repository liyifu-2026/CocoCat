mod transport;
mod agent_manager;
mod agent_registry;
mod message_bus;

use agent_registry::AgentRegistry;
use message_bus::ChatMessage;
use serde_json::json;
use std::time::Instant;

fn main() {
    println!("CocoCat Core starting...\n");

    // Ensure required directories exist
    let _ = std::fs::create_dir_all("chat");
    let _ = std::fs::create_dir_all("agents/dispatch_queue");
    let _ = std::fs::create_dir_all("agents/dispatch_messages");

    let configs = AgentRegistry::load_config("agents/config.toml")
        .expect("failed to load agent config");
    println!("Loaded {} agent definitions\n", configs.len());

    for cfg in &configs {
        let status = if cfg.enabled { "enabled" } else { "disabled" };
        println!("  [{status}] {} ({})", cfg.name, cfg.id);
    }
    println!();

    let mut registry = AgentRegistry::new(configs);
    match registry.start_all() {
        Ok(()) => {}
        Err(e) => eprintln!("Warning: some agents failed to spawn: {e}"),
    }

    let running = registry.status().iter().filter(|s| s.running).count();
    println!("Spawned {running} agents\n");

    // Ping all
    println!("--- Health Check ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        let ok = agent.call("ping", None, 0)
            .ok()
            .and_then(|r| r.result)
            .map(|r| r.get("pong") == Some(&json!(true)))
            .unwrap_or(false);
        let tick = if ok { "\u{2705}" } else { "\u{274C}" };
        println!("  {} {} ({})", tick, cfg.name, cfg.id);
    }
    println!();

    // Identify all
    println!("--- Team Roster ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        if let Some(data) = agent.call("identify", None, 0).ok().and_then(|r| r.result) {
            let name = data.get("name").and_then(|v| v.as_str()).unwrap_or("?");
            let id = data.get("id").and_then(|v| v.as_str()).unwrap_or("?");
            let scene = data.get("scene").and_then(|v| v.as_str()).unwrap_or("?");
            println!("  {}: id={id}, name={name}, scene={scene}", cfg.id);
        }
    }
    println!();

    // === Message Bus Demo ===
    println!("--- Message Bus Demo ---");

    // System: team online
    message_bus::log_message(&ChatMessage {
        timestamp: chrono::Utc::now().to_rfc3339(),
        from: "system".to_string(),
        to: "*".to_string(),
        content: "Team online. Message bus active.".to_string(),
        message_type: "system".to_string(),
    }).ok();

    // Send a task to leader that uses dispatch_task tool
    if let Some(agent) = registry.get("leader") {
        let prompt = concat!(
            "You are the team leader (组长). Your team: employee_a (员工A) and employee_b (员工B).\n\n",
            "Use your dispatch_task tool to send this EXACT message to employee_a:\n",
            "\"Hello 员工A, this is a test message from the group chat. Please confirm you received this by responding with 'Message received by employee_a'.\"\n\n",
            "After using dispatch_task, tell me what you did."
        );
        let params = json!({"prompt": prompt});
        let start = Instant::now();
        match agent.call("task", Some(params), 1) {
            Ok(resp) => {
                let elapsed = start.elapsed();
                message_bus::log_message(&ChatMessage {
                    timestamp: chrono::Utc::now().to_rfc3339(),
                    from: "leader".to_string(),
                    to: "*".to_string(),
                    content: format!("Task completed in {:.1}s", elapsed.as_secs_f64()),
                    message_type: "system".to_string(),
                }).ok();

                if let Some(ref result) = resp.result {
                    let content = result["content"].as_str().unwrap_or("(no content)");
                    let iterations = result["iterations"].as_u64().unwrap_or(0);
                    println!("\n  Leader completed in {iterations} iterations ({:.1}s):\n", elapsed.as_secs_f64());
                    for line in content.lines() {
                        println!("    {line}");
                    }

                    // Process any dispatch requests the agent created
                    println!();
                    check_and_process_dispatches(&mut registry);
                } else if let Some(ref err) = resp.error {
                    println!("  Leader error [{}]: {}", err.code, err.message);
                }
            }
            Err(e) => {
                println!("  Leader task failed: {e}");
            }
        }
    }
    println!();

    // Show recent chat log
    println!("--- Chat Log ---");
    match message_bus::read_recent(20) {
        Ok(messages) => {
            for msg in &messages {
                let from = if msg.from == "system" { "●" } else { &msg.from };
                let to = if msg.to == "*" { "team" } else { &msg.to };
                println!("  [{from} -> {to}] {}", msg.content);
            }
        }
        Err(e) => println!("  Failed to read chat log: {e}"),
    }
    println!();

    println!("CocoCat Core exiting.");
}

/// Check dispatch queue and forward messages to target agents
fn check_and_process_dispatches(registry: &mut AgentRegistry) {
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

        // Log the dispatch
        message_bus::log_message(&ChatMessage {
            timestamp: chrono::Utc::now().to_rfc3339(),
            from: "leader".to_string(),
            to: target_id.clone(),
            content: format!("Dispatching task: {:.80}", prompt),
            message_type: "task".to_string(),
        }).ok();

        println!("  Routing dispatch to '{}'...", target_id);
        match registry.dispatch_message(&target_id, &method, params) {
            Ok(response) => {
                println!("  \u{2705} Dispatch to '{}' succeeded", target_id);
                if let Some(ref result) = response.result {
                    if let Some(content) = result["content"].as_str() {
                        println!("  Response: {:.120}", content);
                        message_bus::log_message(&ChatMessage {
                            timestamp: chrono::Utc::now().to_rfc3339(),
                            from: target_id.clone(),
                            to: "leader".to_string(),
                            content: content.to_string(),
                            message_type: "reply".to_string(),
                        }).ok();
                    }
                } else if let Some(ref err) = response.error {
                    println!("  \u{274C} Dispatch error [{}]: {}", err.code, err.message);
                    message_bus::log_message(&ChatMessage {
                        timestamp: chrono::Utc::now().to_rfc3339(),
                        from: target_id.clone(),
                        to: "leader".to_string(),
                        content: format!("Error [{}]: {}", err.code, err.message),
                        message_type: "reply".to_string(),
                    }).ok();
                }
            }
            Err(e) => {
                println!("  \u{274C} Dispatch to '{}' failed: {}", target_id, e);
                message_bus::log_message(&ChatMessage {
                    timestamp: chrono::Utc::now().to_rfc3339(),
                    from: "system".to_string(),
                    to: "leader".to_string(),
                    content: format!("Dispatch to {} failed: {}", target_id, e),
                    message_type: "system".to_string(),
                }).ok();
            }
        }

        processed.push(path);
    }

    // Clean up processed dispatch files
    for path in processed {
        let _ = std::fs::remove_file(&path);
    }
}
