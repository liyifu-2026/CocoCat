use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{BufRead, Write};

#[derive(Debug, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub params: Option<Value>,
    pub id: u64,
}

impl JsonRpcRequest {
    pub fn new(method: &str, params: Option<Value>, id: u64) -> Self {
        Self {
            jsonrpc: "2.0".to_string(),
            method: method.to_string(),
            params,
            id,
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<u64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
}

/// Write a JSON-RPC request as a single line to a writer (child's stdin)
pub fn send_request(writer: &mut impl Write, req: &JsonRpcRequest) -> Result<(), String> {
    let line = serde_json::to_string(req).map_err(|e| format!("serialize error: {}", e))?;
    writeln!(writer, "{}", line).map_err(|e| format!("write error: {}", e))?;
    writer.flush().map_err(|e| format!("flush error: {}", e))
}

/// Read a JSON-RPC response from a buffered reader (child's stdout)
pub fn read_response(reader: &mut impl BufRead) -> Result<JsonRpcResponse, String> {
    let mut line = String::new();
    reader
        .read_line(&mut line)
        .map_err(|e| format!("read error: {}", e))?;
    if line.is_empty() {
        return Err("EOF: child process closed stdout".to_string());
    }
    serde_json::from_str(&line).map_err(|e| format!("deserialize error: {}", e))
}
