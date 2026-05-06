use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StreamEvent {
    pub event_type: String,
    pub content: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub input: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<String>,
}

impl StreamEvent {
    pub fn progress(content: String) -> Self {
        Self { event_type: "stream_progress".into(), content, name: None, input: None, status: None, result: None }
    }
    pub fn tool(name: String, input: String, status: String, result: String) -> Self {
        Self { event_type: "stream_tool".into(), content: String::new(), name: Some(name), input: Some(input), status: Some(status), result: Some(result) }
    }
    pub fn reasoning(content: String) -> Self {
        Self { event_type: "stream_reasoning".into(), content, name: None, input: None, status: None, result: None }
    }
}
