use cococat::errors::AgentError;

#[test]
fn test_io_error_display() {
    let io_err = std::io::Error::new(std::io::ErrorKind::NotFound, "file not found");
    let err = AgentError::IoError(io_err);
    let msg = format!("{}", err);
    assert!(msg.contains("IO error"));
    assert!(msg.contains("file not found"));
}

#[test]
fn test_serialization_error_display() {
    let ser_err = serde_json::from_str::<String>("invalid json").unwrap_err();
    let err = AgentError::SerializationError(ser_err);
    let msg = format!("{}", err);
    assert!(msg.contains("Serialization error"));
}

#[test]
fn test_agent_crashed_display() {
    let err = AgentError::AgentCrashed("segfault".to_string());
    assert_eq!(format!("{}", err), "Agent crashed: segfault");
}

#[test]
fn test_timeout_display() {
    let err = AgentError::Timeout("agent call timed out".to_string());
    assert_eq!(format!("{}", err), "Timeout: agent call timed out");
}

#[test]
fn test_stdin_closed_display() {
    let err = AgentError::StdinClosed("stdin closed".to_string());
    assert_eq!(format!("{}", err), "Stdin closed: stdin closed");
}

#[test]
fn test_config_error_display() {
    let err = AgentError::ConfigError("agent not found".to_string());
    assert_eq!(format!("{}", err), "Config error: agent not found");
}

#[test]
fn test_error_impl_std_error() {
    use std::error::Error;
    let err = AgentError::ConfigError("test".to_string());
    let cause = err.source();
    assert!(cause.is_none());
}

#[test]
fn test_from_io_error() {
    let io_err = std::io::Error::new(std::io::ErrorKind::PermissionDenied, "permission denied");
    let agent_err: AgentError = io_err.into();
    match agent_err {
        AgentError::IoError(_) => assert!(true),
        _ => panic!("expected IoError variant"),
    }
}

#[test]
fn test_from_serde_error() {
    let ser_err = serde_json::from_str::<i32>("not_a_number").unwrap_err();
    let agent_err: AgentError = ser_err.into();
    match agent_err {
        AgentError::SerializationError(_) => assert!(true),
        _ => panic!("expected SerializationError variant"),
    }
}
