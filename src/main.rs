mod transport;
mod agent_manager;

use agent_manager::AgentProcess;

fn main() {
    println!("CocoCat Core starting...");

    let mut agent = AgentProcess::spawn("python", "py-agent/agent_runtime.py")
        .expect("failed to spawn agent");

    println!("Agent spawned, sending ping...");

    let ping_response = agent
        .call("ping", None, 1)
        .expect("failed to communicate with agent");

    println!(
        "Ping response: {}",
        serde_json::to_string_pretty(&ping_response).unwrap()
    );

    if let Some(result) = ping_response.result {
        if result.get("pong") == Some(&serde_json::json!(true)) {
            println!("MVP PASSED: Rust ↔ Python communication verified!");
        }
    }

    println!("\nTesting echo with parameters...");

    let echo_params = serde_json::json!({
        "message": "hello from Rust",
        "value": 42
    });

    let echo_response = agent
        .call("echo", Some(echo_params.clone()), 2)
        .expect("failed to echo");

    println!(
        "Echo response: {}",
        serde_json::to_string_pretty(&echo_response).unwrap()
    );

    if echo_response.result == Some(echo_params) {
        println!("ECHO PASSED: bi-directional parameter passing verified!");
    } else {
        println!("ECHO FAILED: response did not match");
    }

    println!("CocoCat Core exiting.");
}
