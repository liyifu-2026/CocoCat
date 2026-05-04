use cococat::message_bus::{self, ChatMessage};
use std::fs;

#[test]
fn test_new_message_creates_valid_message() {
    let msg = message_bus::new_message(
        "test_agent".to_string(),
        "user".to_string(),
        "hello world".to_string(),
        "text".to_string(),
    );
    assert_eq!(msg.from, "test_agent");
    assert_eq!(msg.to, "user");
    assert_eq!(msg.content, "hello world");
    assert_eq!(msg.message_type, "text");
    assert!(msg.msg_id.starts_with("msg_"));
    assert!(msg.task_id.is_none());
    assert!(!msg.timestamp.is_empty());
}

#[test]
fn test_new_message_increments_id() {
    let msg1 = message_bus::new_message("a".to_string(), "b".to_string(), "first".to_string(), "text".to_string());
    let msg2 = message_bus::new_message("a".to_string(), "b".to_string(), "second".to_string(), "text".to_string());
    assert_ne!(msg1.msg_id, msg2.msg_id);
}

#[test]
fn test_message_json_roundtrip() {
    let msg = ChatMessage {
        msg_id: "msg_roundtrip".to_string(),
        task_id: Some(42),
        timestamp: "2026-01-01T00:00:00Z".to_string(),
        from: "alice".to_string(),
        to: "bob".to_string(),
        content: "ping".to_string(),
        message_type: "text".to_string(),
    };
    let json = serde_json::to_string(&msg).unwrap();
    let deserialized: ChatMessage = serde_json::from_str(&json).unwrap();
    assert_eq!(deserialized.msg_id, msg.msg_id);
    assert_eq!(deserialized.task_id, msg.task_id);
    assert_eq!(deserialized.from, msg.from);
    assert_eq!(deserialized.to, msg.to);
    assert_eq!(deserialized.content, msg.content);
    assert_eq!(deserialized.message_type, msg.message_type);
}

#[test]
fn test_message_with_task_id() {
    let msg = ChatMessage {
        msg_id: "msg_42".to_string(),
        task_id: Some(99),
        timestamp: "2026-01-01T00:00:00Z".to_string(),
        from: "system".to_string(),
        to: "*".to_string(),
        content: "task complete".to_string(),
        message_type: "system".to_string(),
    };
    assert_eq!(msg.task_id, Some(99));
    let json = serde_json::to_string(&msg).unwrap();
    assert!(json.contains("\"task_id\":99"));
}

#[test]
fn test_message_default_task_id_is_none() {
    let msg = message_bus::new_message("a".to_string(), "b".to_string(), "test".to_string(), "text".to_string());
    assert!(msg.task_id.is_none());
}

#[test]
fn test_deserialize_message_without_optional_fields() {
    let json = r#"{"msg_id":"msg_1","timestamp":"2026-01-01T00:00:00Z","from":"a","to":"b","content":"hi","message_type":"text"}"#;
    let msg: ChatMessage = serde_json::from_str(json).unwrap();
    assert_eq!(msg.from, "a");
    assert_eq!(msg.content, "hi");
    assert!(msg.task_id.is_none());
}

#[test]
fn test_deserialize_message_with_all_fields() {
    let json = r#"{"msg_id":"msg_1","task_id":7,"timestamp":"2026-01-01T00:00:00Z","from":"a","to":"b","content":"hi","message_type":"text"}"#;
    let msg: ChatMessage = serde_json::from_str(json).unwrap();
    assert_eq!(msg.task_id, Some(7));
}

#[test]
fn test_log_and_read_messages() {
    let original_path = "chat/group.jsonl";
    let backup = fs::read_to_string(original_path).unwrap_or_default();

    let msg1 = message_bus::new_message("alice".to_string(), "bob".to_string(), "first_msg".to_string(), "text".to_string());
    let msg2 = message_bus::new_message("bob".to_string(), "alice".to_string(), "second_msg".to_string(), "reply".to_string());

    let _ = message_bus::log_message(&msg1);
    let _ = message_bus::log_message(&msg2);

    let recent = message_bus::read_recent(10).unwrap();
    let last_two: Vec<&ChatMessage> = recent.iter().rev().take(2).collect();
    assert_eq!(last_two[0].content, "second_msg");
    assert_eq!(last_two[1].content, "first_msg");

    let _ = fs::write(original_path, backup);
}

#[test]
fn test_read_recent_handles_empty_log() {
    let original_path = "chat/group.jsonl";
    let backup = fs::read_to_string(original_path).unwrap_or_default();

    fs::write(original_path, "").unwrap();
    let recent = message_bus::read_recent(10).unwrap();
    assert_eq!(recent.len(), 0);

    let _ = fs::write(original_path, backup);
}
