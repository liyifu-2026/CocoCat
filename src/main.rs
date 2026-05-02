mod transport;
mod agent_manager;
mod agent_registry;

use agent_registry::AgentRegistry;
use serde_json::json;

fn main() {
    println!("CocoCat Core starting...\n");

    // 1. Load agent configs
    let configs = AgentRegistry::load_config("agents/config.toml")
        .expect("failed to load agent config");
    println!("Loaded {} agent definitions\n", configs.len());

    for cfg in &configs {
        let status = if cfg.enabled { "enabled" } else { "disabled" };
        println!("  [{status}] {} ({})", cfg.name, cfg.id);
    }
    println!();

    // 2. Spawn all agents
    let mut registry = AgentRegistry::new(configs);
    match registry.start_all() {
        Ok(()) => {}
        Err(e) => eprintln!("Warning: some agents failed to spawn: {e}"),
    }

    let running = registry.status().iter().filter(|s| s.running).count();
    println!("Spawned {running} agents\n");

    // 3. Ping all
    println!("--- Health Check ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        let ok = agent.call("ping", None, 0)
            .ok()
            .and_then(|r| r.result)
            .map(|r| r.get("pong") == Some(&json!(true)))
            .unwrap_or(false);
        println!("  {} {} ({})", if ok { "\u{2705}" } else { "\u{274C}" }, cfg.name, cfg.id);
    }
    println!();

    // 4. Identify all
    println!("--- Team Roster ---");
    for cfg in registry.configs.clone() {
        if !cfg.enabled { continue; }
        let Some(agent) = registry.get(&cfg.id) else { continue; };
        if let Some(data) = agent.call("identify", None, 0).ok().and_then(|r| r.result) {
            let name = data.get("name").and_then(|v| v.as_str()).unwrap_or("?");
            let id = data.get("id").and_then(|v| v.as_str()).unwrap_or("?");
            println!("  {}: id={id}, name={name}", cfg.id);
        }
    }
    println!();

    // 5. Leader demo: manage team schedule using tools
    println!("--- Leader Schedule Management ---");
    if let Some(agent) = registry.get("leader") {
        let prompt = concat!(
            "You are the team leader (组长). Your team has 3 members: yourself (leader), employee_a (员工A), and employee_b (员工B).\n\n",
            "Please do the following:\n",
            "1. Read the file agents/schedule.json to see the current schedule\n",
            "2. The schedule is empty. Create a new schedule for today by writing to agents/schedule.json:\n",
            "   - Task: 'Review PR #42' assigned to employee_a\n",
            "   - Task: 'Write unit tests' assigned to employee_b\n",
            "   - Task: 'Team standup' assigned to leader\n",
            "3. Read the file back to confirm it was written correctly\n",
            "4. Tell me the current team status and what everyone is working on\n\n",
            "Use your read_file and write_file tools to complete these steps."
        );
        let params = json!({"prompt": prompt});
        match agent.call("task", Some(params), 1) {
            Ok(resp) => {
                if let Some(result) = resp.result {
                    let content = result.get("content").and_then(|c| c.as_str()).unwrap_or("(no content)");
                    let iterations = result.get("iterations").and_then(|i| i.as_u64()).unwrap_or(0);
                    println!("  Leader completed in {iterations} iterations.\n");
                    for line in content.lines() {
                        println!("    {line}");
                    }
                } else if let Some(err) = resp.error {
                    println!("  Error [{}]: {}", err.code, err.message);
                }
            }
            Err(e) => {
                println!("  Leader task failed: {e}");
            }
        }
    }
    println!();

    // 6. Show final schedule
    println!("--- Final Schedule ---");
    match std::fs::read_to_string("agents/schedule.json") {
        Ok(content) => {
            for line in content.lines() {
                println!("  {line}");
            }
        }
        Err(e) => println!("  Failed to read schedule: {e}"),
    }
    println!();

    println!("CocoCat Core exiting.");
}
