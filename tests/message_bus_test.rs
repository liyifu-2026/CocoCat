use cococat::message_bus::ChatMessage;

#[test]
fn test_chat_message_creation() {
    let msg = ChatMessage {
        timestamp: "2026-01-01T00:00:00Z".to_string(),
        from: "leader".to_string(),
        to: "*".to_string(),
        content: "Hello team".to_string(),
        message_type: "system".to_string(),
    };
    assert_eq!(msg.from, "leader");
}

#[test]
fn test_chat_message_serialization() {
    let msg = ChatMessage {
        timestamp: "2026-01-01T00:00:00Z".to_string(),
        from: "a".to_string(), to: "b".to_string(),
        content: "hi".to_string(), message_type: "text".to_string(),
    };
    let json = serde_json::to_string(&msg).unwrap();
    assert!(json.contains("\"from\":\"a\""));
}

#[test]
fn test_chat_message_deserialization() {
    let json = r#"{"timestamp":"2026-01-01T00:00:00Z","from":"leader","to":"*","content":"hi","message_type":"text"}"#;
    let msg: ChatMessage = serde_json::from_str(json).unwrap();
    assert_eq!(msg.from, "leader");
}
