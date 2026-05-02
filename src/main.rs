mod transport;
mod agent_manager;

use agent_manager::AgentProcess;
use serde_json::json;

fn main() {
    println!("CocoCat Core starting...\n");

    // --- Ping test ---
    let mut agent = AgentProcess::spawn("python", "py-agent/agent_runtime.py")
        .expect("failed to spawn agent");

    println!("[1/3] Ping test...");
    let ping_resp = agent.call("ping", None, 1).expect("ping failed");
    let pong_ok = ping_resp
        .result
        .map(|r| r.get("pong") == Some(&json!(true)))
        .unwrap_or(false);
    println!("  {} Ping OK\n", if pong_ok { "✅" } else { "❌" });

    // --- Echo test ---
    println!("[2/3] Echo test...");
    let echo_params = json!({"message": "hello from Rust", "value": 42});
    let echo_resp = agent
        .call("echo", Some(echo_params.clone()), 2)
        .expect("echo failed");
    let echo_ok = echo_resp.result == Some(echo_params);
    println!("  {} Echo OK\n", if echo_ok { "✅" } else { "❌" });

    // --- Task test ---
    println!("[3/3] Task test (requires OPENAI_API_KEY)...");
    let task_params = json!({
        "prompt": "Respond with exactly: Task infrastructure is working. List your available tools."
    });
    let task_resp = agent.call("task", Some(task_params), 3);

    match task_resp {
        Ok(resp) => {
            if let Some(result) = resp.result {
                let content = result.get("content").and_then(|c| c.as_str()).unwrap_or("(no content)");
                let iterations = result.get("iterations").and_then(|i| i.as_u64()).unwrap_or(0);
                println!("  Agent response ({iterations} iterations):");
                for line in content.lines() {
                    println!("    {line}");
                }
                println!();
            } else if let Some(err) = resp.error {
                println!("  Agent error [{}]: {}", err.code, err.message);
            }
        }
        Err(e) => {
            println!("  Task call failed (expected if no OPENAI_API_KEY): {e}");
        }
    }

    println!("CocoCat Core exiting.");
}
