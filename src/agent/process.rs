use crate::agent::stream_event::StreamEvent;
use crate::db::models::Agent;
use crate::dispatch::engine::WsEvent;
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

pub struct AgentProcess {
    pub agent_id: String,
    child: Child,
    stdin_writer: Option<std::process::ChildStdin>,
    stdout_receiver: mpsc::Receiver<String>,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: String,
    pub method: String,
    pub params: Value,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct JsonRpcError {
    pub code: i64,
    pub message: String,
}

impl AgentProcess {
    pub fn spawn(config: &Agent) -> Result<Self, String> {
        let python = if Command::new("python3")
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .and_then(|mut c| c.wait())
            .map(|s| s.success())
            .unwrap_or(false)
        {
            "python3"
        } else {
            "python"
        };

        let mut child = Command::new(python)
            .arg("-u")
            .arg("py-agent/agent_runtime.py")
            .arg("--agent-id")
            .arg(&config.id)
            .arg("--model")
            .arg(&config.model)
            .arg("--scene-id")
            .arg(&config.scene_id)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn agent {}: {}", config.id, e))?;

        let stdin_writer = child.stdin.take()
            .ok_or_else(|| "Failed to take stdin".to_string())?;

        let stderr = child.stderr.take()
            .ok_or_else(|| "Failed to take stderr".to_string())?;

        let stdout = child.stdout.take()
            .ok_or_else(|| "Failed to take stdout".to_string())?;

        let agent_id = config.id.clone();

        // Background thread: continuously reads stdout and sends lines through channel.
        // Created once at spawn, reused for all call() invocations.
        let (tx, stdout_receiver) = mpsc::channel::<String>();
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                match line {
                    Ok(l) => {
                        if tx.send(l).is_err() {
                            break; // receiver dropped
                        }
                    }
                    Err(_) => break, // EOF or error
                }
            }
        });

        // Stderr forwarder
        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                if let Ok(line) = line {
                    eprintln!("[{}:stderr] {}", agent_id, line);
                }
            }
        });

        Ok(Self {
            agent_id: config.id.clone(),
            child,
            stdin_writer: Some(stdin_writer),
            stdout_receiver,
        })
    }

    pub fn call(
        &mut self,
        method: &str,
        params: Value,
        timeout_secs: u64,
    ) -> Result<Value, String> {
        let request = JsonRpcRequest {
            jsonrpc: "2.0".into(),
            id: uuid::Uuid::new_v4().to_string(),
            method: method.into(),
            params,
        };

        let request_line = serde_json::to_string(&request)
            .map_err(|e| format!("serialize request: {}", e))?;

        if let Some(ref mut stdin) = self.stdin_writer {
            writeln!(stdin, "{}", request_line)
                .map_err(|e| format!("write to stdin: {}", e))?;
            stdin.flush().map_err(|e| format!("flush stdin: {}", e))?;
        } else {
            return Err("stdin closed".to_string());
        }

        // Read one response line from the persistent background reader
        let line = if timeout_secs > 0 {
            match self.stdout_receiver.recv_timeout(Duration::from_secs(timeout_secs)) {
                Ok(l) => l,
                Err(mpsc::RecvTimeoutError::Timeout) => {
                    return Err(format!(
                        "Agent {} call timed out after {}s",
                        self.agent_id, timeout_secs
                    ));
                }
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    return Err("Agent stdout channel disconnected".to_string());
                }
            }
        } else {
            self.stdout_receiver.recv()
                .map_err(|_| "Agent stdout channel disconnected".to_string())?
        };

        let response: JsonRpcResponse = serde_json::from_str(&line)
            .map_err(|e| format!("parse JSON-RPC response: {} (raw: {})", e, line))?;

        if let Some(err) = response.error {
            return Err(format!("Agent error: {} (code {})", err.message, err.code));
        }

        Ok(response.result.unwrap_or(Value::Null))
    }

    pub fn call_stream(
        &mut self,
        method: &str,
        params: Value,
        timeout_secs: u64,
        ws_tx: &tokio::sync::broadcast::Sender<WsEvent>,
        task_uuid: &str,
    ) -> Result<Value, String> {
        let request = JsonRpcRequest {
            jsonrpc: "2.0".into(),
            id: uuid::Uuid::new_v4().to_string(),
            method: method.into(),
            params,
        };

        let request_line = serde_json::to_string(&request)
            .map_err(|e| format!("serialize request: {}", e))?;

        if let Some(ref mut stdin) = self.stdin_writer {
            writeln!(stdin, "{}", request_line)
                .map_err(|e| format!("write to stdin: {}", e))?;
            stdin.flush().map_err(|e| format!("flush stdin: {}", e))?;
        } else {
            return Err("stdin closed".to_string());
        }

        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(timeout_secs);

        loop {
            if std::time::Instant::now() > deadline {
                return Err(format!("Agent {} call timed out after {}s", self.agent_id, timeout_secs));
            }

            let remaining = deadline - std::time::Instant::now();
            let line = self.stdout_receiver
                .recv_timeout(remaining.max(std::time::Duration::from_secs(1)))
                .map_err(|e| match e {
                    mpsc::RecvTimeoutError::Timeout => {
                        format!("Agent {} call timed out", self.agent_id)
                    }
                    mpsc::RecvTimeoutError::Disconnected => {
                        "Agent stdout channel disconnected".to_string()
                    }
                })?;

            let parsed: serde_json::Value = serde_json::from_str(&line)
                .map_err(|e| format!("parse line: {} (raw: {})", e, line))?;

            if parsed.get("jsonrpc").and_then(|v| v.as_str()) == Some("2.0") {
                // Final JSON-RPC response
                let response: JsonRpcResponse = serde_json::from_str(&line)
                    .map_err(|e| format!("parse JSON-RPC response: {} (raw: {})", e, line))?;
                if let Some(err) = response.error {
                    return Err(format!("Agent error: {} (code {})", err.message, err.code));
                }
                return Ok(response.result.unwrap_or(Value::Null));
            }

            // Forward stream events to WebSocket in real-time
            if let Some(etype) = parsed.get("type").and_then(|v| v.as_str()) {
                let stream_event = match etype {
                    "progress" => Some(StreamEvent::progress(
                        parsed.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    )),
                    "tool" => Some(StreamEvent::tool(
                        parsed.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        parsed.get("input").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        parsed.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        parsed.get("result").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    )),
                    "reasoning" => Some(StreamEvent::reasoning(
                        parsed.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                    )),
                    _ => None,
                };
                if let Some(se) = stream_event {
                    let ws_event = WsEvent {
                        event: se.event_type.clone(),
                        task_uuid: task_uuid.to_string(),
                        status: "streaming".into(),
                        result: None,
                        error: None,
                        stream_event: Some(se),
                    };
                    let _ = ws_tx.send(ws_event);
                }
            }
        }
    }

    pub fn is_running(&mut self) -> bool {
        match self.child.try_wait() {
            Ok(Some(_)) => false,
            _ => true,
        }
    }

    pub fn kill(&mut self) -> Result<(), String> {
        let _ = self.stdin_writer.take();
        self.child.kill().map_err(|e| format!("kill agent: {}", e))?;
        let _ = self.child.wait();
        Ok(())
    }
}

impl Drop for AgentProcess {
    fn drop(&mut self) {
        let _ = self.stdin_writer.take();
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
