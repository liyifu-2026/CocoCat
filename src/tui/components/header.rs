use ratatui::{
    layout::Rect,
    style::Style,
    text::{Line, Span},
    widgets::{Block, Paragraph},
    Frame,
};
use crate::theme::theme::Theme;

pub fn render_header(f: &mut Frame, area: Rect, agent: &str, theme: &Theme) {
    let text = format!(" cococat · {} ", agent);
    let block = Block::default()
        .style(Style::default().bg(theme.surface()));
    let paragraph = Paragraph::new(Line::from(Span::styled(
        text,
        Style::default().fg(theme.accent_color()),
    )))
    .block(block);
    f.render_widget(paragraph, area);
}
