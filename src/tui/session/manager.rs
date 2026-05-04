use std::path::PathBuf;
use serde::{Serialize, Deserialize};
use chrono::Local;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Session {
    pub key: String,
    pub messages: Vec<SessionMessage>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionMessage {
    pub role: String,
    pub content: String,
    pub timestamp: String,
}

impl Session {
    pub fn new(key: &str) -> Self {
        let now = Local::now().format("%Y-%m-%dT%H:%M:%S").to_string();
        Session {
            key: key.to_string(),
            messages: vec![],
            created_at: now.clone(),
            updated_at: now,
        }
    }

    pub fn add_message(&mut self, role: &str, content: &str) {
        self.messages.push(SessionMessage {
            role: role.to_string(),
            content: content.to_string(),
            timestamp: Local::now().format("%H:%M:%S").to_string(),
        });
        self.updated_at = Local::now().format("%Y-%m-%dT%H:%M:%S").to_string();
    }
}

pub struct SessionManager {
    sessions_dir: PathBuf,
}

impl SessionManager {
    pub fn new() -> Self {
        let base = dirs::home_dir().unwrap_or_default().join(".cococat");
        SessionManager { sessions_dir: base.join("sessions") }
    }

    pub fn list(&self) -> Vec<String> {
        let dir = &self.sessions_dir;
        if !dir.exists() { return vec![]; }
        let mut sessions: Vec<String> = std::fs::read_dir(dir)
            .ok()
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().map(|ext| ext == "jsonl").unwrap_or(false))
            .filter_map(|e| e.path().file_stem().map(|s| s.to_string_lossy().to_string()))
            .collect();
        sessions.sort();
        sessions
    }

    pub fn load(&self, key: &str) -> Result<Session, String> {
        let path = self.sessions_dir.join(format!("{key}.jsonl"));
        if !path.exists() {
            return Ok(Session::new(key));
        }
        let content = std::fs::read_to_string(&path).map_err(|e| format!("read session: {e}"))?;
        let mut session = Session::new(key);
        for line in content.lines() {
            if line.trim().is_empty() { continue; }
            if let Ok(msg) = serde_json::from_str::<SessionMessage>(line) {
                session.messages.push(msg);
            }
        }
        Ok(session)
    }

    pub fn save(&self, session: &Session) -> Result<(), String> {
        std::fs::create_dir_all(&self.sessions_dir).map_err(|e| format!("create sessions dir: {e}"))?;
        let path = self.sessions_dir.join(format!("{}.jsonl", session.key));
        let mut content = String::new();
        for msg in &session.messages {
            content.push_str(&serde_json::to_string(msg).map_err(|e| format!("serialize: {e}"))?);
            content.push('\n');
        }
        std::fs::write(&path, content).map_err(|e| format!("write session: {e}"))?;
        Ok(())
    }

    pub fn delete(&self, key: &str) -> Result<(), String> {
        let path = self.sessions_dir.join(format!("{key}.jsonl"));
        if path.exists() {
            std::fs::remove_file(&path).map_err(|e| format!("delete session: {e}"))
        } else {
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_session_create() {
        let s = Session::new("test-session");
        assert_eq!(s.key, "test-session");
        assert!(s.messages.is_empty());
    }

    #[test]
    fn test_session_add_message() {
        let mut s = Session::new("test");
        s.add_message("user", "hello");
        assert_eq!(s.messages.len(), 1);
        assert_eq!(s.messages[0].role, "user");
    }

    #[test]
    fn test_session_serialize_roundtrip() {
        let mut s = Session::new("roundtrip");
        s.add_message("user", "hello");
        s.add_message("assistant", "world");
        let json = serde_json::to_string(&s).unwrap();
        let deserialized: Session = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.key, "roundtrip");
        assert_eq!(deserialized.messages.len(), 2);
    }
}
