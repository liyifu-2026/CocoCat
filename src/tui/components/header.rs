use ratatui::{
    layout::Rect,
    style::{Color, Style},
    text::{Line, Span},
    widgets::{Block, Paragraph},
    Frame,
};
use crate::theme::theme::Theme;

const BLOCK_BG: Color = Color::Rgb(0x2a, 0x2a, 0x2a);

pub fn render_header(f: &mut Frame, area: Rect, agent: &str, theme: &Theme) {
    let text = format!(" cococat · {} ", agent);
    let block = Block::default()
        .style(Style::default().bg(BLOCK_BG));
    let paragraph = Paragraph::new(Line::from(Span::styled(
        text,
        Style::default().fg(theme.accent_color()),
    )))
    .block(block);
    f.render_widget(paragraph, area);
}
