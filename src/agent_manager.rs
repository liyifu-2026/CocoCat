use crate::errors::AgentError;
use cococat::transport::{JsonRpcRequest, JsonRpcResponse};
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};

pub struct AgentProcess {
    child: Child,
    stdin_writer: Option<ChildStdin>,
    stdout_reader: Option<BufReader<std::process::ChildStdout>>,
    #[allow(dead_code)]
    interpreter: String,
}

#[allow(dead_code)]
impl AgentProcess {
    /// Spawn an agent subprocess. `interpreter` is the program to run (e.g. "python"),
    /// `python_script_path` is the path to the agent runtime script,
    /// and `extra_args` are additional CLI arguments passed after the script path.
    pub fn spawn(
        interpreter: &str,
        python_script_path: &str,
        extra_args: &[&str],
    ) -> Result<Self, String> {
        let mut cmd = Command::new(interpreter);
        cmd.arg("-u").arg(python_script_path);
        for arg in extra_args {
            cmd.arg(arg);
        }
        let mut child = cmd
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| format!("failed to spawn agent: {}", e))?;

        let stdin_writer = child.stdin.take().ok_or("failed to open agent stdin")?;
        let stdout_reader =
            BufReader::new(child.stdout.take().ok_or("failed to open agent stdout")?);

        Ok(Self {
            child,
            stdin_writer: Some(stdin_writer),
            stdout_reader: Some(stdout_reader),
            interpreter: interpreter.to_string(),
        })
    }

    /// Send a JSON-RPC request and read the response
    pub fn call(
        &mut self,
        method: &str,
        params: Option<serde_json::Value>,
        id: u64,
        timeout_secs: u64,
    ) -> Result<JsonRpcResponse, AgentError> {
        let req = JsonRpcRequest::new(method, params, id);
        let line = serde_json::to_string(&req)?;
        let writer = self.stdin_writer.as_mut()
            .ok_or_else(|| AgentError::StdinClosed("stdin closed".to_string()))?;
        writeln!(writer, "{}", line)?;
        writer.flush()?;

        let mut reader = self.stdout_reader.take()
            .ok_or_else(|| AgentError::StdinClosed("stdout reader unavailable".to_string()))?;

        if timeout_secs == 0 {
            let mut response_line = String::new();
            let read_result = reader.read_line(&mut response_line);
            self.stdout_reader = Some(reader);
            if let Err(e) = read_result {
                return Err(AgentError::IoError(e));
            }
            if response_line.is_empty() {
                return Err(AgentError::AgentCrashed("child process closed stdout".to_string()));
            }
            let response: JsonRpcResponse = serde_json::from_str(&response_line)?;
            return Ok(response);
        }

        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::spawn(move || {
            let mut line = String::new();
            let result = reader.read_line(&mut line);
            let _ = tx.send((reader, line, result));
        });

        let duration = std::time::Duration::from_secs(timeout_secs);
        match rx.recv_timeout(duration) {
            Ok((reader, response_line, read_result)) => {
                self.stdout_reader = Some(reader);
                if let Err(e) = read_result {
                    return Err(AgentError::IoError(e));
                }
                if response_line.is_empty() {
                    return Err(AgentError::AgentCrashed("child process closed stdout".to_string()));
                }
                let response: JsonRpcResponse = serde_json::from_str(&response_line)?;
                Ok(response)
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                let _ = self.child.kill();
                Err(AgentError::Timeout("agent call timed out".to_string()))
            }
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                Err(AgentError::AgentCrashed("read thread disconnected".to_string()))
            }
        }
    }

    /// Check if process has exited without blocking. Returns true if still running.
    pub fn is_running(&mut self) -> bool {
        match self.child.try_wait() {
            Ok(None) => true,
            _ => false,
        }
    }

    /// Terminate the agent subprocess
    pub fn kill(&mut self) -> Result<(), String> {
        self.child
            .kill()
            .map_err(|e| format!("failed to kill agent: {}", e))
    }

    /// Close stdin, then wait for the agent subprocess to exit
    pub fn wait(&mut self) -> Result<(), String> {
        drop(self.stdin_writer.take());
        self.child
            .wait()
            .map_err(|e| format!("failed to wait for agent: {}", e))?;
        Ok(())
    }
}

impl Drop for AgentProcess {
    fn drop(&mut self) {
        drop(self.stdin_writer.take());
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}
