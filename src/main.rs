mod transport;
mod agent_manager;

use agent_manager::AgentProcess;

fn main() {
    println!("CocoCat Core starting...");

    let mut agent = AgentProcess::spawn("python", "py-agent/agent_runtime.py")
        .expect("failed to spawn agent");

    println!("Agent spawned, sending ping...");

    let response = agent
        .call("ping", None, 1)
        .expect("failed to communicate with agent");

    println!("Response: {}", serde_json::to_string_pretty(&response).unwrap());

    if let Some(result) = response.result {
        if result.get("pong") == Some(&serde_json::json!(true)) {
            println!("MVP PASSED: Rust ↔ Python communication verified!");
        }
    }

    // AgentProcess Drop impl will kill and wait automatically
    println!("CocoCat Core exiting.");
}
