use ratatui::{
    layout::Rect,
    style::Style,
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph, Wrap},
    Frame,
};
use crate::app::ChatMessage;
use crate::event::TuiEvent;
use crate::theme::theme::Theme;

pub fn render_chat_panel(
    f: &mut Frame,
    area: Rect,
    messages: &[ChatMessage],
    scroll_offset: usize,
    theme: &Theme,
) {
    let block = Block::default()
        .title(" Chat ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.border_color()));

    let inner = block.inner(area);

    let mut lines: Vec<Line> = Vec::new();

    for msg in messages {
        if msg.role == "user" {
            lines.push(Line::from(Span::styled(
                msg.timestamp.clone(),
                theme.style_text_dim(),
            )));
            for content_line in msg.content.lines() {
                lines.push(Line::from(Span::styled(
                    content_line.to_string(),
                    theme.style_accent(),
                )));
            }
        } else {
            for event in &msg.events {
                match event {
                    TuiEvent::Delta(text) => {
                        for line in text.lines() {
                            lines.push(Line::from(Span::raw(line.to_string())));
                        }
                    }
                    TuiEvent::Reasoning(text) => {
                        for line in text.lines() {
                            lines.push(Line::from(Span::styled(
                                format!("  {}", line),
                                theme.style_think(),
                            )));
                        }
                    }
                    TuiEvent::ToolStart { tool, args } => {
                        let display = if args.is_empty() {
                            format!("  ◈ {}", tool)
                        } else {
                            format!("  ◈ {} ({})", tool, args)
                        };
                        lines.push(Line::from(Span::styled(display, theme.style_tool())));
                    }
                    TuiEvent::ToolDone { tool, result } => {
                        let preview = if result.len() > 80 {
                            format!("{}...", &result[..80])
                        } else {
                            result.clone()
                        };
                        let display = format!("  ✓ {} — {}", tool, preview);
                        lines.push(Line::from(Span::styled(display, theme.style_success())));
                    }
                    TuiEvent::ToolError { tool, error } => {
                        let display = format!("  ✗ {}: {}", tool, error);
                        lines.push(Line::from(Span::styled(display, theme.style_error())));
                    }
                    _ => {}
                }
            }
        }
    }

    let available_height = inner.height as usize;
    let start = scroll_offset.min(lines.len().saturating_sub(1));
    let end = (start + available_height).min(lines.len());

    let visible: Vec<Line> = if start < lines.len() {
        lines[start..end].to_vec()
    } else {
        vec![]
    };

    let paragraph = Paragraph::new(visible)
        .block(block)
        .wrap(Wrap { trim: false });

    f.render_widget(paragraph, area);
}

pub fn calculate_message_height(width: u16, content: &str, is_user: bool, _theme: &Theme) -> u16 {
    let effective = width.saturating_sub(4).max(1) as usize;
    let mut lines = 0u16;
    if is_user {
        lines += 1;
    }
    if content.is_empty() {
        return lines.max(1);
    }
    for line in content.lines() {
        lines += ((line.chars().count() + effective - 1) / effective) as u16;
    }
    lines.max(1)
}
