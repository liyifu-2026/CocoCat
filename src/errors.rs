use std::fmt;

#[derive(Debug)]
pub enum AgentError {
    IoError(std::io::Error),
    SerializationError(serde_json::Error),
    AgentCrashed(String),
    Timeout(String),
    StdinClosed(String),
    ConfigError(String),
}

impl fmt::Display for AgentError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AgentError::IoError(e) => write!(f, "IO error: {e}"),
            AgentError::SerializationError(e) => write!(f, "Serialization error: {e}"),
            AgentError::AgentCrashed(msg) => write!(f, "Agent crashed: {msg}"),
            AgentError::Timeout(msg) => write!(f, "Timeout: {msg}"),
            AgentError::StdinClosed(msg) => write!(f, "Stdin closed: {msg}"),
            AgentError::ConfigError(msg) => write!(f, "Config error: {msg}"),
        }
    }
}

impl std::error::Error for AgentError {}

impl From<std::io::Error> for AgentError {
    fn from(e: std::io::Error) -> Self { AgentError::IoError(e) }
}

impl From<serde_json::Error> for AgentError {
    fn from(e: serde_json::Error) -> Self { AgentError::SerializationError(e) }
}
