use ratatui::{
    layout::Rect,
    style::{Color, Style},
    text::{Line, Span},
    widgets::{Block, Paragraph},
    Frame,
};
use crate::theme::theme::Theme;

const BLOCK_BG: Color = Color::Rgb(0x2a, 0x2a, 0x2a);

pub fn status_text(agent: &str, model: &str, theme_name: &str) -> String {
    format!(" {} | {} | {} ", agent, model, theme_name)
}

pub fn render_status_bar(f: &mut Frame, area: Rect, agent_id: &str, model: &str, theme: &Theme) {
    let block = Block::default()
        .style(Style::default().bg(BLOCK_BG));

    let status = status_text(agent_id, model, &theme.name);
    let paragraph = Paragraph::new(Line::from(Span::raw(status))).block(block);

    f.render_widget(paragraph, area);
}
