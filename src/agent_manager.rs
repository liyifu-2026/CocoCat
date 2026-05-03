use crate::transport::{self, JsonRpcRequest, JsonRpcResponse};
use std::io::BufReader;
use std::process::{Child, ChildStdin, Command, Stdio};

pub struct AgentProcess {
    child: Child,
    stdin_writer: Option<ChildStdin>,
    stdout_reader: BufReader<std::process::ChildStdout>,
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
            stdout_reader,
            interpreter: interpreter.to_string(),
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
        transport::send_request(self.stdin_writer.as_mut().unwrap(), &req)?;
        transport::read_response(&mut self.stdout_reader)
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
