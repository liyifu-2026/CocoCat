#[derive(Debug, Clone)]
pub enum TuiEvent {
    Delta(String),
    Reasoning(String),
    ToolStart { tool: String, args: String },
    ToolDone { tool: String, result: String },
    ToolError { tool: String, error: String },
    Progress(String),
    Done(String),
    JsonRpcDone(String),
    JsonRpcError(String),
}

impl TuiEvent {
    pub fn from_json_line(line: &str) -> Option<Self> {
        let v: serde_json::Value = serde_json::from_str(line).ok()?;
        let obj = v.as_object()?;

        if let Some(ev) = obj.get("event").and_then(|v| v.as_str()) {
            match ev {
                "delta" => Some(TuiEvent::Delta(
                    obj.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                )),
                "reasoning" => Some(TuiEvent::Reasoning(
                    obj.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                )),
                "tool_start" => Some(TuiEvent::ToolStart {
                    tool: obj.get("tool").and_then(|v| v.as_str()).unwrap_or("?").to_string(),
                    args: obj.get("args").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                }),
                "tool_done" => Some(TuiEvent::ToolDone {
                    tool: obj.get("tool").and_then(|v| v.as_str()).unwrap_or("?").to_string(),
                    result: obj.get("result").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                }),
                "tool_error" => Some(TuiEvent::ToolError {
                    tool: obj.get("tool").and_then(|v| v.as_str()).unwrap_or("?").to_string(),
                    error: obj.get("result").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                }),
                "progress" => Some(TuiEvent::Progress(
                    obj.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                )),
                "done" => Some(TuiEvent::Done(
                    obj.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                )),
                _ => None,
            }
        } else if obj.contains_key("jsonrpc") {
            if let Some(result) = obj.get("result") {
                if result.get("streamed") == Some(&serde_json::Value::Bool(true)) {
                    let content = result.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    return Some(TuiEvent::JsonRpcDone(content));
                }
                let content = serde_json::to_string(result).unwrap_or_default();
                return Some(TuiEvent::JsonRpcDone(content));
            }
            if let Some(err) = obj.get("error") {
                let msg = err.get("message").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();
                return Some(TuiEvent::JsonRpcError(msg));
            }
            None
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_delta_event() {
        let line = r#"{"event":"delta","content":"Hello "}"#;
        let e = TuiEvent::from_json_line(line).unwrap();
        assert!(matches!(e, TuiEvent::Delta(s) if s == "Hello "));
    }

    #[test]
    fn test_parse_reasoning_event() {
        let line = r#"{"event":"reasoning","content":"thinking..."}"#;
        let e = TuiEvent::from_json_line(line).unwrap();
        assert!(matches!(e, TuiEvent::Reasoning(s) if s == "thinking..."));
    }

    #[test]
    fn test_parse_tool_start() {
        let line = r#"{"event":"tool_start","tool":"read_file","args":"path=test"}"#;
        let e = TuiEvent::from_json_line(line).unwrap();
        assert!(matches!(e, TuiEvent::ToolStart { tool, .. } if tool == "read_file"));
    }

    #[test]
    fn test_parse_tool_done() {
        let line = r#"{"event":"tool_done","tool":"read_file","result":"file content"}"#;
        let e = TuiEvent::from_json_line(line).unwrap();
        assert!(matches!(e, TuiEvent::ToolDone { tool, .. } if tool == "read_file"));
    }

    #[test]
    fn test_parse_done() {
        let line = r#"{"event":"done","content":"final answer"}"#;
        let e = TuiEvent::from_json_line(line).unwrap();
        assert!(matches!(e, TuiEvent::Done(s) if s == "final answer"));
    }

    #[test]
    fn test_parse_invalid_json() {
        let line = "not json";
        assert!(TuiEvent::from_json_line(line).is_none());
    }

    #[test]
    fn test_parse_jsonrpc_done() {
        let line = r#"{"jsonrpc":"2.0","result":{"streamed":true,"content":"done"}}"#;
        let e = TuiEvent::from_json_line(line).unwrap();
        assert!(matches!(e, TuiEvent::JsonRpcDone(s) if s == "done"));
    }
}
