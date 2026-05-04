use ratatui::{
    layout::Rect,
    style::Style,
    text::{Line, Span},
    widgets::{Block, Paragraph},
    Frame,
};
use crate::theme::theme::Theme;

pub fn status_text(agent: &str, model: &str, theme_name: &str) -> String {
    format!(" {} | {} | {} ", agent, model, theme_name)
}

pub fn render_status_bar(f: &mut Frame, area: Rect, agent_id: &str, model: &str, theme: &Theme) {
    let block = Block::default()
        .style(Style::default().bg(theme.surface()));

    let status = status_text(agent_id, model, &theme.name);
    let paragraph = Paragraph::new(Line::from(Span::raw(status))).block(block);

    f.render_widget(paragraph, area);
}
