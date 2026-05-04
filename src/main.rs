use cococat::message_bus;
mod agent_manager;
mod agent_registry;
mod dispatcher;
mod errors;
mod hire;
mod logging;
mod signal;

use agent_registry::AgentRegistry;
use serde_json::json;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

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

    tracing::info!("[Question] {}", q_text);
    let answer = if !options.is_empty() {
        for (i, opt) in options.iter().enumerate() {
            tracing::info!("  {}. {}", i + 1, opt);
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
    if let Ok(s) = serde_json::to_string_pretty(&response) {
        if let Err(e) = std::fs::write(question_path, &s) {
            tracing::warn!("Failed to write question response: {e}");
        }
    }
    println!();
}

fn main() {
    println!("CocoCat Core starting...\n");

    if let Err(e) = std::fs::create_dir_all("chat") {
        tracing::warn!("Failed to create chat dir: {e}");
    }
    if let Err(e) = std::fs::create_dir_all("agents/dispatch_queue") {
        tracing::warn!("Failed to create dispatch_queue dir: {e}");
    }
    if let Err(e) = std::fs::create_dir_all("agents/dispatch_messages") {
        tracing::warn!("Failed to create dispatch_messages dir: {e}");
    }

    message_bus::init_counter();
    logging::init();

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

    let running_count = registry.status().iter().filter(|s| s.running).count();
    println!("Spawned {running_count} agents\n");

    println!("--- Health Check ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        let ok = agent.call("ping", None, 0, 5)
            .ok()
            .and_then(|r| r.result)
            .map(|r| r.get("pong") == Some(&json!(true)))
            .unwrap_or(false);
        let tick = if ok { "\u{2705}" } else { "\u{274C}" };
        println!("  {} {} ({})", tick, cfg.name, cfg.id);
    }
    println!();

    println!("--- Team Roster ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        if let Some(data) = agent.call("identify", None, 0, 5).ok().and_then(|r| r.result) {
            let name = data.get("name").and_then(|v| v.as_str()).unwrap_or("?");
            let pid = data.get("id").and_then(|v| v.as_str()).unwrap_or("?");
            let scene = data.get("scene").and_then(|v| v.as_str()).unwrap_or("?");
            println!("  {}: id={pid}, name={name}, scene={scene}", cfg.id);
        }
    }
    println!();

    println!("--- Chat Log ---");
    match message_bus::read_recent(20) {
        Ok(messages) => {
            for msg in &messages {
                let from = if msg.from == "system" { "\u{25CF}" } else { &msg.from };
                let to = if msg.to == "*" { "team" } else { &msg.to };
                println!("  [{from} -> {to}] {}", msg.content);
            }
        }
        Err(e) => println!("  Failed to read chat log: {e}"),
    }
    println!();

    println!("--- Entering Daemon Mode (type 'quit' or 'exit' to stop) ---");

    let running = signal::setup();
    setup_shutdown_handler(running.clone());

    let mut last_health_check = Instant::now();
    let health_check_interval = std::time::Duration::from_secs(15);

    while running.load(Ordering::Relaxed) {
        if last_health_check.elapsed() >= health_check_interval {
            let restarted = registry.health_check();
            if !restarted.is_empty() {
                tracing::info!("Health check: restarted {} agents", restarted.len());
            }
            last_health_check = Instant::now();
        }

        dispatcher::check_and_process_dispatches(&mut registry);
        hire::process_pending_hires();
        hire::process_hire_requests(&mut registry);
        check_user_questions();
        message_bus::get_and_persist_counter();

        std::thread::sleep(std::time::Duration::from_secs(5));
    }

    tracing::info!("Shutting down...");
    message_bus::get_and_persist_counter();
    tracing::info!("CocoCat Core exiting.");
}

fn setup_shutdown_handler(running: Arc<AtomicBool>) {
    let r = running.clone();
    std::thread::spawn(move || {
        let mut input = String::new();
        while r.load(Ordering::Relaxed) {
            input.clear();
            match std::io::stdin().read_line(&mut input) {
                Ok(_) => {
                    let trimmed = input.trim();
                    if trimmed.eq_ignore_ascii_case("quit") || trimmed.eq_ignore_ascii_case("exit") {
                        r.store(false, Ordering::Relaxed);
                        break;
                    }
                }
                Err(_) => {
                    r.store(false, Ordering::Relaxed);
                    break;
                }
            }
        }
    });
}
