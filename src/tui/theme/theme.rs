use ratatui::prelude::Stylize;
use ratatui::style::{Color, Style};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Theme {
    pub name: String,
    pub colors: ThemeColors,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThemeColors {
    pub background: String,
    pub surface: String,
    pub text: String,
    pub text_dim: String,
    pub accent: String,
    pub success: String,
    pub error: String,
    pub warning: String,
    pub user_bubble: String,
    pub agent_bubble: String,
    pub border: String,
    pub selection: String,
    pub scrollbar: String,
    pub thinking: String,
    pub tool: String,
    pub code_bg: String,
}

impl Default for Theme {
    fn default() -> Self {
        Theme {
            name: "catppuccin-mocha".into(),
            colors: ThemeColors {
                background: "#1e1e2e".into(), surface: "#313244".into(), text: "#cdd6f4".into(),
                text_dim: "#6c7086".into(), accent: "#89b4fa".into(), success: "#a6e3a1".into(),
                error: "#f38ba8".into(), warning: "#fab387".into(), user_bubble: "#45475a".into(),
                agent_bubble: "#313244".into(), border: "#585b70".into(), selection: "#585b70".into(),
                scrollbar: "#45475a".into(), thinking: "#6c7086".into(), tool: "#89b4fa".into(),
                code_bg: "#181825".into(),
            },
        }
    }
}

impl ThemeColors {
    pub fn hex_to_rgb(hex: &str) -> Color {
        let hex = hex.trim_start_matches('#');
        if hex.len() == 6 {
            if let Ok(r) = u8::from_str_radix(&hex[0..2], 16) {
                if let Ok(g) = u8::from_str_radix(&hex[2..4], 16) {
                    if let Ok(b) = u8::from_str_radix(&hex[4..6], 16) {
                        return Color::Rgb(r, g, b);
                    }
                }
            }
        }
        Color::Reset
    }
}

impl Theme {
    pub fn style_text(&self) -> Style { Style::default().fg(ThemeColors::hex_to_rgb(&self.colors.text)) }
    pub fn style_text_dim(&self) -> Style { Style::default().fg(ThemeColors::hex_to_rgb(&self.colors.text_dim)) }
    pub fn style_accent(&self) -> Style { Style::default().fg(ThemeColors::hex_to_rgb(&self.colors.accent)) }
    pub fn style_success(&self) -> Style { Style::default().fg(ThemeColors::hex_to_rgb(&self.colors.success)) }
    pub fn style_error(&self) -> Style { Style::default().fg(ThemeColors::hex_to_rgb(&self.colors.error)) }
    pub fn style_warning(&self) -> Style { Style::default().fg(ThemeColors::hex_to_rgb(&self.colors.warning)) }
    pub fn style_think(&self) -> Style { Style::default().fg(ThemeColors::hex_to_rgb(&self.colors.thinking)).italic() }
    pub fn style_tool(&self) -> Style { Style::default().fg(ThemeColors::hex_to_rgb(&self.colors.tool)) }
    pub fn bg(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.background) }
    pub fn surface(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.surface) }
    pub fn border_color(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.border) }
    pub fn accent_color(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.accent) }
    pub fn text_dim_color(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.text_dim) }
    pub fn text_color(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.text) }
    pub fn error_color(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.error) }
    pub fn tool_color(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.tool) }
    pub fn scrollbar_color(&self) -> Color { ThemeColors::hex_to_rgb(&self.colors.scrollbar) }
}

pub struct ThemeRegistry {
    themes: Vec<Theme>,
    current_index: usize,
}

impl ThemeRegistry {
    pub fn new() -> Self {
        let themes = crate::theme::builtin::builtin_themes();
        ThemeRegistry { themes, current_index: 0 }
    }

    pub fn current(&self) -> &str { &self.themes[self.current_index].name }
    pub fn current_theme(&self) -> &Theme { &self.themes[self.current_index] }
    pub fn get(&self, name: &str) -> Option<&Theme> {
        self.themes.iter().find(|t| t.name == name)
    }
    pub fn all(&self) -> &[Theme] { &self.themes }
    pub fn switch(&mut self, name: &str) -> bool {
        if let Some(i) = self.themes.iter().position(|t| t.name == name) {
            self.current_index = i;
            true
        } else { false }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_theme_default() {
        let theme = Theme::default();
        assert_eq!(theme.name, "catppuccin-mocha");
        assert_eq!(theme.colors.background, "#1e1e2e");
        assert_eq!(theme.colors.text, "#cdd6f4");
    }

    #[test]
    fn test_theme_from_json() {
        let json = r##"{"name":"custom","colors":{"background":"#000","surface":"#111","text":"#fff","accent":"#0ff","success":"#0f0","error":"#f00","warning":"#ff0","thinking":"#666","tool":"#0ff","code_bg":"#000","text_dim":"#666","user_bubble":"#222","agent_bubble":"#111","border":"#333","selection":"#444","scrollbar":"#555"}}"##;
        let theme: Theme = serde_json::from_str(json).unwrap();
        assert_eq!(theme.name, "custom");
    }

    #[test]
    fn test_hex_to_rgb() {
        let color = ThemeColors::hex_to_rgb("#cdd6f4");
        assert_eq!(color, Color::Rgb(205, 214, 244));
    }

    #[test]
    fn test_theme_registry() {
        let registry = ThemeRegistry::new();
        assert!(registry.get("catppuccin-mocha").is_some());
        assert!(registry.get("nonexistent").is_none());
        assert_eq!(registry.current(), "catppuccin-mocha");
    }

    #[test]
    fn test_theme_switch() {
        let mut registry = ThemeRegistry::new();
        assert!(registry.switch("nord"));
        assert_eq!(registry.current(), "nord");
        assert!(!registry.switch("nonexistent"));
        assert_eq!(registry.current(), "nord");
    }
}
