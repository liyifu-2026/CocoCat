use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default)]
    pub chat: ChatConfig,
    #[serde(default)]
    pub display: DisplayConfig,
    #[serde(default)]
    pub daemon: DaemonConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatConfig {
    #[serde(default = "default_agent")]
    pub default_agent: String,
    #[serde(default = "default_true")]
    pub session_persistence: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisplayConfig {
    #[serde(default = "default_true")]
    pub render_markdown: bool,
    #[serde(default = "default_true")]
    pub show_progress: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DaemonConfig {
    #[serde(default = "default_cargo")]
    pub cargo_path: String,
}

fn default_agent() -> String { "leader".to_string() }
fn default_true() -> bool { true }
fn default_cargo() -> String { "cargo".to_string() }

impl Default for Config {
    fn default() -> Self {
        Config {
            chat: ChatConfig { default_agent: default_agent(), session_persistence: true },
            display: DisplayConfig { render_markdown: true, show_progress: true },
            daemon: DaemonConfig { cargo_path: default_cargo() },
        }
    }
}

impl Default for ChatConfig { fn default() -> Self { ChatConfig { default_agent: default_agent(), session_persistence: true } } }
impl Default for DisplayConfig { fn default() -> Self { DisplayConfig { render_markdown: true, show_progress: true } } }
impl Default for DaemonConfig { fn default() -> Self { DaemonConfig { cargo_path: default_cargo() } } }

impl Config {
    pub fn load_or_default<P: AsRef<Path>>(path: P) -> Result<Config, String> {
        let path = path.as_ref();
        if !path.exists() {
            return Ok(Config::default());
        }
        let content = std::fs::read_to_string(path).map_err(|e| format!("read config: {e}"))?;
        serde_json::from_str(&content).map_err(|e| format!("parse config: {e}"))
    }

    pub fn config_path() -> std::path::PathBuf {
        let base = dirs::home_dir().unwrap_or_default().join(".cococat");
        base.join("config.json")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let cfg = Config::default();
        assert_eq!(cfg.chat.default_agent, "leader");
        assert_eq!(cfg.display.render_markdown, true);
        assert_eq!(cfg.display.show_progress, true);
    }

    #[test]
    fn test_config_deserialize() {
        let json = r#"{
            "chat": { "default_agent": "builder", "session_persistence": true },
            "display": { "render_markdown": true, "show_progress": false },
            "daemon": { "cargo_path": "cargo" }
        }"#;
        let cfg: Config = serde_json::from_str(json).unwrap();
        assert_eq!(cfg.chat.default_agent, "builder");
        assert_eq!(cfg.display.show_progress, false);
    }

    #[test]
    fn test_config_load_nonexistent() {
        let cfg = Config::load_or_default("/nonexistent/path/config.json");
        assert!(cfg.is_ok());
        assert_eq!(cfg.unwrap().chat.default_agent, "leader");
    }
}
