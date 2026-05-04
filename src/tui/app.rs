use crate::event::TuiEvent;
use crate::theme::theme::ThemeRegistry;
use crate::types::stats::{ToolStats, SessionStats, SystemStats, ToolCallInfo};

#[derive(Debug, Clone)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
    pub events: Vec<TuiEvent>,
    pub is_streaming: bool,
    pub timestamp: String,
}

impl ChatMessage {
    pub fn new_user(content: String) -> Self {
        ChatMessage {
            role: "user".into(),
            content,
            events: vec![],
            is_streaming: false,
            timestamp: chrono::Local::now().format("%H:%M:%S").to_string(),
        }
    }

    pub fn new_assistant() -> Self {
        ChatMessage {
            role: "assistant".into(),
            content: String::new(),
            events: vec![],
            is_streaming: true,
            timestamp: chrono::Local::now().format("%H:%M:%S").to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct AgentStatus {
    pub id: String,
    pub name: String,
    pub running: bool,
}

pub enum InputMode {
    Normal,
}

pub enum Dialog {
    ThemeSelector,
    Help,
    SessionSwitcher,
    ModelSelector,
}

#[derive(Debug, Clone)]
pub struct SidebarSection {
    pub name: String,
    pub collapsed: bool,
}

impl SidebarSection {
    pub fn new(name: &str) -> Self {
        SidebarSection { name: name.to_string(), collapsed: false }
    }
    pub fn toggle(&mut self) { self.collapsed = !self.collapsed; }
}

pub struct App {
    pub agent_id: String,
    pub messages: Vec<ChatMessage>,
    pub input: String,
    pub input_mode: InputMode,
    pub show_sidebar: bool,
    pub sidebar_auto: bool,
    pub sidebar_sections: Vec<SidebarSection>,
    pub theme_registry: ThemeRegistry,
    pub scroll_offset: usize,
    pub should_quit: bool,
    pub status_message: String,
    pub dialog: Option<Dialog>,
    pub tool_stats: ToolStats,
    pub session_stats: SessionStats,
    pub system_stats: SystemStats,
    pub agent_statuses: Vec<AgentStatus>,
}

impl App {
    pub fn new(agent_id: &str) -> Self {
        App {
            agent_id: agent_id.to_string(),
            messages: vec![],
            input: String::new(),
            input_mode: InputMode::Normal,
            show_sidebar: false,
            sidebar_auto: true,
            sidebar_sections: vec![
                SidebarSection::new("Team"),
                SidebarSection::new("Session"),
                SidebarSection::new("Tools"),
                SidebarSection::new("Mail"),
            ],
            theme_registry: ThemeRegistry::new(),
            scroll_offset: 0,
            should_quit: false,
            status_message: String::new(),
            dialog: None,
            tool_stats: ToolStats::default(),
            session_stats: SessionStats::default(),
            system_stats: SystemStats::default(),
            agent_statuses: vec![],
        }
    }

    pub fn track_tool_start(&mut self, tool_name: &str) {
        if let Some(tc) = self.tool_stats.tool_calls.iter_mut().find(|t| t.name == tool_name) {
            tc.status = "running".to_string();
            tc.count += 1;
        } else {
            self.tool_stats.tool_calls.push(ToolCallInfo {
                name: tool_name.to_string(),
                status: "running".to_string(),
                count: 1,
            });
        }
    }

    pub fn track_tool_done(&mut self, tool_name: &str) {
        if let Some(tc) = self.tool_stats.tool_calls.iter_mut().find(|t| t.name == tool_name) {
            tc.status = "done".to_string();
        }
    }

    pub fn track_tool_error(&mut self, tool_name: &str) {
        if let Some(tc) = self.tool_stats.tool_calls.iter_mut().find(|t| t.name == tool_name) {
            tc.status = "error".to_string();
        }
    }

    pub fn add_user_message(&mut self, content: String) {
        self.messages.push(ChatMessage::new_user(content));
        self.scroll_to_bottom();
    }

    pub fn start_assistant_message(&mut self) {
        self.messages.push(ChatMessage::new_assistant());
    }

    pub fn append_to_last(&mut self, event: TuiEvent) {
        if let Some(msg) = self.messages.last_mut() {
            if msg.role == "assistant" {
                match &event {
                    TuiEvent::Delta(s) => msg.content.push_str(s),
                    _ => {}
                }
                msg.events.push(event);
            }
        }
    }

    pub fn finalize_last_message(&mut self) {
        if let Some(msg) = self.messages.last_mut() {
            msg.is_streaming = false;
        }
    }

    pub fn switch_theme(&mut self, name: &str) -> bool {
        self.theme_registry.switch(name)
    }

    pub fn scroll_to_bottom(&mut self) {
        self.scroll_offset = usize::MAX;
    }

    pub fn toggle_sidebar(&mut self) {
        if self.sidebar_auto {
            self.sidebar_auto = false;
            self.show_sidebar = false;
        } else if !self.show_sidebar {
            self.show_sidebar = true;
        } else {
            self.sidebar_auto = true;
            self.show_sidebar = false;
        }
    }

    pub fn quit(&mut self) {
        self.should_quit = true;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_app_initial_state() {
        let app = App::new("leader");
        assert_eq!(app.agent_id, "leader");
        assert_eq!(app.messages.len(), 0);
        assert!(!app.show_sidebar);
    }

    #[test]
    fn test_app_add_message() {
        let mut app = App::new("leader");
        app.add_user_message("hello".to_string());
        assert_eq!(app.messages.len(), 1);
        assert_eq!(app.messages[0].role, "user");
    }

    #[test]
    fn test_app_switch_theme() {
        let mut app = App::new("leader");
        assert!(app.switch_theme("nord"));
        assert_eq!(app.theme_registry.current(), "nord");
        assert!(!app.switch_theme("nonexistent"));
    }
}
