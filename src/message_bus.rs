use serde::{Deserialize, Serialize};
use std::io::Write;
use std::sync::atomic::{AtomicU64, Ordering};

static MSG_COUNTER: AtomicU64 = AtomicU64::new(0);

fn load_counter() -> u64 {
    std::fs::read_to_string("chat/.counter")
        .ok()
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or(0)
}

fn save_counter(val: u64) {
    if let Err(e) = std::fs::write("chat/.counter", val.to_string()) {
        tracing::warn!("Failed to write counter: {e}");
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub msg_id: String,
    #[serde(default)]
    pub task_id: Option<u64>,
    pub timestamp: String,
    pub from: String,
    pub to: String,
    pub content: String,
    pub message_type: String,
}

/// Log a chat message with atomic write (tmp + rename)
pub fn log_message(msg: &ChatMessage) -> Result<(), String> {
    let line = serde_json::to_string(msg).map_err(|e| format!("serialize error: {}", e))?;

    let chat_path = std::path::Path::new("chat/group.jsonl");
    let tmp_path = std::path::Path::new("chat/group.jsonl.tmp");

    let existing = std::fs::read_to_string(chat_path).unwrap_or_default();
    let mut tmp_file = std::fs::File::create(tmp_path)
        .map_err(|e| format!("failed to create tmp file: {}", e))?;
    tmp_file.write_all(existing.as_bytes())
        .map_err(|e| format!("failed to write tmp: {}", e))?;
    writeln!(tmp_file, "{}", line)
        .map_err(|e| format!("write error: {}", e))?;
    tmp_file.sync_all()
        .map_err(|e| format!("sync error: {}", e))?;
    std::fs::rename(tmp_path, chat_path)
        .map_err(|e| format!("rename error: {}", e))?;

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

/// Create a new ChatMessage with auto-generated ID
pub fn new_message(from: String, to: String, content: String, message_type: String) -> ChatMessage {
    let counter = MSG_COUNTER.fetch_add(1, Ordering::Relaxed);
    ChatMessage {
        msg_id: format!("msg_{:06}", counter),
        task_id: None,
        timestamp: chrono::Utc::now().to_rfc3339(),
        from,
        to,
        content,
        message_type,
    }
}

/// Initialize the message counter from disk
pub fn init_counter() {
    let val = load_counter();
    MSG_COUNTER.store(val, Ordering::Relaxed);
}

/// Get current counter value and persist to disk
pub fn get_and_persist_counter() -> u64 {
    let val = MSG_COUNTER.load(Ordering::Relaxed);
    save_counter(val);
    val
}
