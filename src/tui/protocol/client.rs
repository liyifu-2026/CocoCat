use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;

use crate::event::TuiEvent;

pub struct AgentClient {
    child: Option<Child>,
    runtime_path: String,
}

impl AgentClient {
    pub fn new(project_dir: &str) -> Self {
        let runtime_path = format!("{}/py-agent/agent_runtime.py", project_dir);
        AgentClient { child: None, runtime_path }
    }

    pub fn build_request(agent_id: &str, prompt: &str) -> String {
        let v = serde_json::json!({
            "jsonrpc": "2.0",
            "method": "chat",
            "params": { "agent_id": agent_id, "content": prompt },
            "id": 1
        });
        v.to_string() + "\n"
    }

    pub fn build_ping_request(_agent_id: &str) -> String {
        let v = serde_json::json!({
            "jsonrpc": "2.0",
            "method": "ping",
            "params": null,
            "id": 1
        });
        v.to_string() + "\n"
    }

    pub fn send_stream(
        &mut self,
        agent_id: &str,
        prompt: &str,
        tx: mpsc::Sender<TuiEvent>,
    ) -> Result<(), String> {
        let mut child = Command::new("python3")
            .args(["-u", &self.runtime_path, "--agent-id", agent_id])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("spawn agent: {e}"))?;

        let mut stdin = child.stdin.as_mut().ok_or("no stdin")?;
        let request = Self::build_request(agent_id, prompt);
        stdin.write_all(request.as_bytes()).map_err(|e| format!("write request: {e}"))?;

        let stdout = child.stdout.take().ok_or("no stdout")?;
        let stderr = child.stderr.take().ok_or("no stderr")?;
        let tx_clone = tx.clone();

        // Read stderr for errors
        std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                if let Ok(line) = line {
                    let line = line.trim().to_string();
                    if !line.is_empty() {
                        let _ = tx_clone.send(TuiEvent::Progress(format!("[agent] {}", line)));
                    }
                }
            }
        });

        let tx_clone2 = tx.clone();

        // Read stdout for response
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                match line {
                    Ok(line) => {
                        let line = line.trim().to_string();
                        if line.is_empty() { continue; }
                        if let Some(event) = TuiEvent::from_json_line(&line) {
                            if tx_clone2.send(event).is_err() { break; }
                        }
                    }
                    Err(_) => break,
                }
            }
            // Send Done if the agent closed without a done event
            let _ = tx_clone2.send(TuiEvent::Done(String::new()));
        });

        self.child = Some(child);
        Ok(())
    }

    pub fn close(&mut self) {
        if let Some(mut child) = self.child.take() {
            // Send shutdown request
            if let Some(stdin) = child.stdin.as_mut() {
                let v = serde_json::json!({
                    "jsonrpc": "2.0", "method": "shutdown", "id": 2
                });
                let _ = writeln!(stdin, "{}", v);
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

impl Drop for AgentClient {
    fn drop(&mut self) {
        self.close();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_protocol_client_creates_request() {
        let request = AgentClient::build_request("leader", "hello");
        assert!(request.contains("chat"));
        assert!(request.contains("hello"));
    }

    #[test]
    fn test_ping_request() {
        let request = AgentClient::build_ping_request("leader");
        assert!(request.contains("ping"));
        assert!(request.contains("jsonrpc"));
    }
}
