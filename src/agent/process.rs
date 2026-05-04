use crate::db::models::Agent;
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

        let agent_id = config.id.clone();
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

        let stdout = self.child.stdout.take()
            .ok_or_else(|| "stdout already taken".to_string())?;

        let (tx, rx) = mpsc::channel();
        thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            let mut line = String::new();
            let result = reader.read_line(&mut line);
            let _ = tx.send((
                reader.into_inner(),
                line,
                result.map_err(|e| e.to_string()),
            ));
        });

        let (stdout, line, read_result) = if timeout_secs > 0 {
            match rx.recv_timeout(Duration::from_secs(timeout_secs)) {
                Ok(v) => v,
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
            rx.recv().map_err(|_| "Agent stdout channel disconnected".to_string())?
        };

        self.child.stdout = Some(stdout);

        read_result?;

        let response: JsonRpcResponse = serde_json::from_str(&line)
            .map_err(|e| format!("parse JSON-RPC response: {} (raw: {})", e, line))?;

        if let Some(err) = response.error {
            return Err(format!("Agent error: {} (code {})", err.message, err.code));
        }

        Ok(response.result.unwrap_or(Value::Null))
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
