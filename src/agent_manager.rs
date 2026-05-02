use crate::transport::{self, JsonRpcRequest, JsonRpcResponse};
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};

pub struct AgentProcess {
    pub child: Child,
    pub stdin_writer: Box<dyn Write + Send>,
    pub stdout_reader: Box<dyn BufRead + Send>,
}

impl AgentProcess {
    /// Spawn a Python agent subprocess. `python_script_path` is the
    /// path to the Python agent runtime file.
    pub fn spawn(python_script_path: &str) -> Result<Self, String> {
        let mut child = Command::new("python")
            .arg("-u") // unbuffered stdout
            .arg(python_script_path)
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
            stdin_writer: Box::new(stdin_writer),
            stdout_reader: Box::new(stdout_reader),
        })
    }

    /// Send a JSON-RPC request and read the response
    pub fn call(
        &mut self,
        method: &str,
        params: Option<serde_json::Value>,
        id: u64,
    ) -> Result<JsonRpcResponse, String> {
        let req = JsonRpcRequest::new(method, params, id);
        transport::send_request(&mut self.stdin_writer, &req)?;
        transport::read_response(&mut self.stdout_reader)
    }

    /// Terminate the agent subprocess
    pub fn kill(&mut self) -> Result<(), String> {
        self.child
            .kill()
            .map_err(|e| format!("failed to kill agent: {}", e))
    }

    /// Wait for the agent subprocess to exit
    pub fn wait(&mut self) -> Result<(), String> {
        self.child
            .wait()
            .map_err(|e| format!("failed to wait for agent: {}", e))?;
        Ok(())
    }
}
