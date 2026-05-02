use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub timestamp: String,
    pub from: String,
    pub to: String,
    pub content: String,
    pub message_type: String, // "task", "reply", "system"
}

/// Log a chat message to chat/group.jsonl
pub fn log_message(msg: &ChatMessage) -> Result<(), String> {
    let line = serde_json::to_string(msg).map_err(|e| format!("serialize error: {}", e))?;
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open("chat/group.jsonl")
        .map_err(|e| format!("failed to open chat log: {}", e))?;
    use std::io::Write;
    writeln!(file, "{}", line).map_err(|e| format!("write error: {}", e))?;
    Ok(())
}

/// Read recent chat messages (last N)
pub fn read_recent(n: usize) -> Result<Vec<ChatMessage>, String> {
    let content = std::fs::read_to_string("chat/group.jsonl")
        .map_err(|e| format!("failed to read chat log: {}", e))?;
    let mut messages: Vec<ChatMessage> = content
        .lines()
        .filter_map(|line| serde_json::from_str(line).ok())
        .collect();
    let len = messages.len();
    if len > n {
        messages = messages.split_off(len - n);
    }
    Ok(messages)
}
