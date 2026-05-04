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

    pub fn build_request(_agent_id: &str, prompt: &str) -> String {
        let v = serde_json::json!({
            "jsonrpc": "2.0",
            "method": "task_stream",
            "params": { "prompt": prompt },
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
            .args(["-u", &self.runtime_path, "--id", agent_id, "--name", agent_id])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("spawn agent: {e}"))?;

        let stdin = child.stdin.as_mut().ok_or("no stdin")?;
        let request = Self::build_request(agent_id, prompt);
        stdin.write_all(request.as_bytes()).map_err(|e| format!("write request: {e}"))?;

        let stdout = child.stdout.take().ok_or("no stdout")?;
        let reader = BufReader::new(stdout);
        let tx_clone = tx.clone();

        std::thread::spawn(move || {
            for line in reader.lines() {
                match line {
                    Ok(line) => {
                        let line = line.trim().to_string();
                        if line.is_empty() { continue; }
                        if let Some(event) = TuiEvent::from_json_line(&line) {
                            if tx_clone.send(event).is_err() { break; }
                        }
                    }
                    Err(_) => break,
                }
            }
        });

        self.child = Some(child);
        Ok(())
    }

    pub fn close(&mut self) {
        if let Some(mut child) = self.child.take() {
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
        assert!(request.contains("jsonrpc"));
        assert!(request.contains("task_stream"));
        assert!(request.contains("hello"));
    }

    #[test]
    fn test_ping_request() {
        let request = AgentClient::build_ping_request("leader");
        assert!(request.contains("ping"));
        assert!(request.contains("jsonrpc"));
    }
}
