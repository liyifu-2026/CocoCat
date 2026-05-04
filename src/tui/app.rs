use crate::event::TuiEvent;
use crate::theme::theme::ThemeRegistry;

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

pub enum InputMode {
    Normal,
}

pub enum SidebarTab {
    Sessions,
    Context,
    Help,
}

pub enum Dialog {
    ThemeSelector,
    Help,
    SessionSwitcher,
}

pub struct App {
    pub agent_id: String,
    pub messages: Vec<ChatMessage>,
    pub input: String,
    pub input_mode: InputMode,
    pub show_sidebar: bool,
    pub sidebar_tab: SidebarTab,
    pub theme_registry: ThemeRegistry,
    pub scroll_offset: usize,
    pub should_quit: bool,
    pub status_message: String,
    pub dialog: Option<Dialog>,
}

impl App {
    pub fn new(agent_id: &str) -> Self {
        App {
            agent_id: agent_id.to_string(),
            messages: vec![],
            input: String::new(),
            input_mode: InputMode::Normal,
            show_sidebar: false,
            sidebar_tab: SidebarTab::Sessions,
            theme_registry: ThemeRegistry::new(),
            scroll_offset: 0,
            should_quit: false,
            status_message: String::new(),
            dialog: None,
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
        self.show_sidebar = !self.show_sidebar;
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
