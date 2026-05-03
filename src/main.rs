use cococat::transport;
use cococat::message_bus;
mod agent_manager;
mod agent_registry;

use agent_registry::AgentRegistry;
use message_bus::ChatMessage;
use serde_json::json;
use std::fs;
use std::time::Instant;

fn process_hire_requests(registry: &mut AgentRegistry) {
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

        println!("  Processing hire: {} ({})", new_name, new_id);

        // 1. Update config.toml
        let config_path = "agents/config.toml";
        let mut config_content = fs::read_to_string(config_path).unwrap_or_default();
        let new_entry = format!(
            "\n[[agents]]\nid = \"{}\"\nname = \"{}\"\ninterpreter = \"python\"\nscript = \"py-agent/agent_runtime.py\"\nenabled = true\nscene = \"default\"\n",
            new_id, new_name
        );
        config_content.push_str(&new_entry);
        if let Err(e) = fs::write(config_path, &config_content) {
            println!("  Failed to update config: {e}");
            continue;
        }

        // 2. Create memory directory
        let mem_dir = format!("agents/{}/memory", new_id);
        let _ = fs::create_dir_all(&mem_dir);
        let _ = fs::write(format!("{}/MEMORY.md", mem_dir), format!("# {} Memory\n\nPersonal memories and learnings.\n", new_name));
        let _ = fs::write(format!("{}/history.jsonl", mem_dir), "");
        let _ = fs::write(format!("{}/.dream_cursor", mem_dir), "0");

        // Write profile.json (immutable — skip if exists)
        let profile_path = format!("agents/{}/profile.json", new_id);
        if !std::path::Path::new(&profile_path).exists() {
            if let Some(p) = hire.get("profile") {
                let mut profile = p.clone();
                if profile.get("gender").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
                    let gender = if new_id.as_bytes().iter().sum::<u8>() % 2 == 0 { "male" } else { "female" };
                    profile["gender"] = serde_json::json!(gender);
                }
                let _ = fs::write(&profile_path, serde_json::to_string_pretty(&profile).unwrap());
            }
        }

        // 3. Spawn the new agent
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
            Ok(()) => println!("  {} ({}) hired and spawned", new_name, new_id),
            Err(e) => println!("  Failed to spawn {}: {}", new_id, e),
        }

        // 4. Log to chat
        let _ = message_bus::log_message(&message_bus::ChatMessage {
            timestamp: chrono::Utc::now().to_rfc3339(),
            from: "system".to_string(),
            to: "*".to_string(),
            content: format!("New team member: {} ({})", new_name, new_id),
            message_type: "system".to_string(),
        });

        // 5. Clean up
        let _ = fs::remove_file(&path);
    }
}

fn check_user_questions() {
    let question_path = std::path::Path::new("agents/_ask_user.json");
    if !question_path.exists() {
        return;
    }
    let content = match std::fs::read_to_string(question_path) {
        Ok(c) => c,
        Err(_) => return,
    };
    let question: serde_json::Value = match serde_json::from_str(&content) {
        Ok(v) => v,
        Err(_) => return,
    };
    let q_text = question.get("question").and_then(|v| v.as_str()).unwrap_or("?").to_string();
    let options: Vec<String> = question.get("options").and_then(|v| v.as_array()).map(|a| {
        a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect()
    }).unwrap_or_default();

    println!("\n[Question] {}", q_text);
    let answer = if !options.is_empty() {
        for (i, opt) in options.iter().enumerate() {
            println!("  {}. {}", i + 1, opt);
        }
        print!("Enter choice (1-{}): ", options.len());
        let _ = std::io::Write::flush(&mut std::io::stdout());
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).ok();
        let input = input.trim().to_string();
        if let Ok(idx) = input.parse::<usize>() {
            if idx >= 1 && idx <= options.len() { options[idx - 1].clone() } else { input }
        } else { input }
    } else {
        print!("Your answer: ");
        let _ = std::io::Write::flush(&mut std::io::stdout());
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).ok();
        input.trim().to_string()
    };

    let response = serde_json::json!({"question": q_text, "answer": answer, "status": "answered"});
    let _ = std::fs::write(question_path, serde_json::to_string_pretty(&response).unwrap());
    println!();
}

fn process_pending_hires() {
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

        println!("\n--- Pending Hire ---");
        println!("  Name:      {name}");
        println!("  ID:        {id}");
        println!("  Role:      {role}");
        println!("  Scene:     {scene}");
        println!("  Traits:    {traits}");
        println!("  Objective: {objective}");
        println!();

        let question_path = std::path::Path::new("agents/_ask_user.json");
        let question = json!({
            "question": format!("Process hire request for '{}' ({})", name, id),
            "options": ["Approve", "Modify and Approve", "Reject"],
            "status": "pending"
        });
        let question_str = match serde_json::to_string_pretty(&question) {
            Ok(s) => s,
            Err(e) => {
                println!("  Failed to serialize question: {e}");
                continue;
            }
        };
        if let Err(e) = fs::write(question_path, question_str) {
            println!("  Failed to write question: {e}");
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
                        let _ = fs::create_dir_all(approved_dir);
                        let dest = approved_dir.join(path.file_name().unwrap());
                        let _ = fs::rename(&path, &dest);
                        let marker_path = format!("{}.processed", dest.display());
                        let _ = fs::write(&marker_path, "{}");
                        println!("  => Approved: {name} ({id})");
                    }
                    _ => {
                        let rejected_dir = std::path::Path::new("agents/hire_requests/rejected");
                        let _ = fs::create_dir_all(rejected_dir);
                        let dest = rejected_dir.join(path.file_name().unwrap());
                        let _ = fs::rename(&path, &dest);
                        let marker_path = format!("{}.processed", dest.display());
                        let _ = fs::write(&marker_path, "{}");
                        println!("  => Rejected: {name} ({id})");
                    }
                }

                let _ = fs::remove_file(question_path);
                break;
            }
        }
    }
}

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
                    process_pending_hires();
                    process_hire_requests(&mut registry);
                    check_user_questions();
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
