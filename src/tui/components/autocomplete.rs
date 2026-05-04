use ratatui::{
    layout::Rect,
    style::Style,
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem},
    Frame,
};
use crate::theme::theme::Theme;

const COMMANDS: &[(&str, &str)] = &[
    ("clear", "Clear chat"),
    ("help", "Show help"),
    ("model", "Select model"),
    ("quit", "Exit"),
    ("theme", "Switch theme"),
    ("session", "Session list"),
];

pub struct AutocompleteState {
    pub visible: bool,
    pub items: Vec<String>,
    pub descriptions: Vec<String>,
    pub selected: usize,
}

impl AutocompleteState {
    pub fn new() -> Self {
        AutocompleteState { visible: false, items: vec![], descriptions: vec![], selected: 0 }
    }

    pub fn reset(&mut self) {
        self.visible = false; self.items.clear(); self.descriptions.clear(); self.selected = 0;
    }

    pub fn trigger(&mut self) {
        self.visible = true;
        self.items = COMMANDS.iter().map(|(n, _)| format!("/{}", n)).collect();
        self.descriptions = COMMANDS.iter().map(|(_, d)| d.to_string()).collect();
        self.selected = 0;
    }

    pub fn filter(&mut self, query: &str) {
        let q = query.to_lowercase();
        self.items = COMMANDS.iter().filter(|(n, _)| format!("/{}", n).contains(&q))
            .map(|(n, _)| format!("/{}", n)).collect();
        self.descriptions = COMMANDS.iter().filter(|(n, _)| format!("/{}", n).contains(&q))
            .map(|(_, d)| d.to_string()).collect();
        if self.selected >= self.items.len() {
            self.selected = self.items.len().saturating_sub(1);
        }
    }

    pub fn previous(&mut self) {
        if self.items.is_empty() { return; }
        self.selected = if self.selected == 0 { self.items.len() - 1 } else { self.selected - 1 };
    }

    pub fn next(&mut self) {
        if self.items.is_empty() { return; }
        self.selected = (self.selected + 1) % self.items.len();
    }

    pub fn selected_command(&self) -> Option<String> {
        if self.items.is_empty() { None } else { Some(self.items[self.selected].clone()) }
    }
}

pub fn render_autocomplete(f: &mut Frame, area: Rect, state: &AutocompleteState, theme: &Theme) {
    if !state.visible || state.items.is_empty() { return; }

    let count = state.items.len().min(10) as u16;
    let width = 36u16;
    let height = count + 2;
    let x = area.x;
    let y = area.y.saturating_sub(height + 1);

    let items: Vec<ListItem> = state.items.iter().enumerate().map(|(i, cmd)| {
        let style = if i == state.selected {
            Style::default().fg(theme.accent_color()).bg(theme.bg())
        } else {
            Style::default().fg(theme.text_color())
        };
        ListItem::new(Line::from(Span::styled(cmd.clone(), style)))
    }).collect();

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.border_color()))
        .title(" Commands ");
    let list = List::new(items).block(block);
    f.render_widget(ratatui::widgets::Clear, Rect::new(x, y, width, height));
    f.render_widget(list, Rect::new(x, y, width, height));
}
