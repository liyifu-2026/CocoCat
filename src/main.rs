mod transport;
mod agent_manager;
mod agent_registry;

use agent_registry::AgentRegistry;
use serde_json::json;

fn main() {
    println!("CocoCat Core starting...\n");

    // 1. Load config
    let configs = AgentRegistry::load_config("agents/config.toml")
        .expect("failed to load agent config");
    println!("Loaded {} agent definitions\n", configs.len());

    for cfg in &configs {
        let status = if cfg.enabled { "enabled" } else { "disabled" };
        println!("  [{status}] {} ({})", cfg.name, cfg.id);
    }
    println!();

    // 2. Spawn agents (allows partial failures)
    let mut registry = AgentRegistry::new(configs);
    match registry.start_all() {
        Ok(()) => {}
        Err(e) => eprintln!("Warning: some agents failed to spawn: {e}"),
    }

    let statuses = registry.status();
    let running_count = statuses.iter().filter(|s| s.running).count();
    println!("Spawned {running_count} agents\n");

    // 3. Ping each running agent
    println!("--- Ping Test ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled {
            continue;
        }
        let Some(agent) = registry.get(&cfg.id) else {
            println!("  ⚠️  {} ({}) not running", cfg.name, cfg.id);
            continue;
        };
        let result = match agent.call("ping", None, 1) {
            Ok(r) => r,
            Err(e) => {
                println!("  ❌ {} ({}): ping failed — {e}", cfg.name, cfg.id);
                continue;
            }
        };
        let is_ok = result
            .result
            .map(|r| r.get("pong") == Some(&json!(true)))
            .unwrap_or(false);
        println!("  {} {} ({})", if is_ok { "✅" } else { "❌" }, cfg.name, cfg.id);
    }
    println!();

    // 4. Identify each running agent
    println!("--- Identity ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled {
            continue;
        }
        let Some(agent) = registry.get(&cfg.id) else {
            continue;
        };
        let result = match agent.call("identify", None, 2) {
            Ok(r) => r,
            Err(_) => continue,
        };
        if let Some(data) = result.result {
            let agent_id = data.get("id").and_then(|v| v.as_str()).unwrap_or("?");
            let agent_name = data.get("name").and_then(|v| v.as_str()).unwrap_or("?");
            println!("  {}: id={agent_id}, name={agent_name}", cfg.id);
        }
    }
    println!();

    // 5. Send a simple task to leader
    println!("--- Task Test (leader) ---");
    let leader_id = "leader".to_string();
    if let Some(agent) = registry.get(&leader_id) {
        let task_params = json!({
            "prompt": "Respond with your identity and list your available tools. Keep it under 100 words."
        });
        match agent.call("task", Some(task_params), 3) {
            Ok(resp) => {
                if let Some(result) = resp.result {
                    let content = result.get("content").and_then(|c| c.as_str()).unwrap_or("(no content)");
                    let iterations = result.get("iterations").and_then(|i| i.as_u64()).unwrap_or(0);
                    println!("  Response from leader ({} iterations):", iterations);
                    for line in content.lines() {
                        println!("    {line}");
                    }
                } else if let Some(err) = resp.error {
                    println!("  Error [{}]: {}", err.code, err.message);
                }
            }
            Err(e) => {
                println!("  Task call failed: {e}");
            }
        }
    }

    println!("\nCocoCat Core exiting.");
}
