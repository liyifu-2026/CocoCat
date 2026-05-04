use ratatui::{
    layout::Rect,
    style::Style,
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph, Scrollbar, ScrollbarOrientation, ScrollbarState, Wrap},
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
    show_scrollbar: bool,
) {
    let block = Block::default()
        .title(" Chat ")
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.border_color()));

    let inner = block.inner(area);

    let lines = build_message_lines(messages, inner.width as usize, theme);

    let available_height = inner.height.max(1) as usize;
    let max_scroll = lines.len().saturating_sub(available_height);
    let scroll = if max_scroll == 0 { 0 } else { scroll_offset.min(max_scroll) };
    let start = scroll;
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

    if show_scrollbar && max_scroll > 0 {
        let scrollbar = Scrollbar::new(ScrollbarOrientation::VerticalRight)
            .begin_symbol(Some("▲"))
            .end_symbol(Some("▼"))
            .track_symbol(Some("│"))
            .thumb_symbol("░")
            .style(Style::default().fg(theme.scrollbar_color()));
        let mut state = ScrollbarState::new(max_scroll).position(scroll);
        f.render_stateful_widget(scrollbar, area, &mut state);
    }
}

fn build_message_lines(messages: &[ChatMessage], _width: usize, theme: &Theme) -> Vec<Line<'static>> {
    let mut lines = Vec::new();
    for msg in messages {
        if msg.role == "user" {
            lines.push(Line::from(Span::styled(
                format!(" {} ", msg.timestamp),
                Style::default().fg(theme.text_dim_color()),
            )));
            lines.push(Line::from(Span::styled(msg.content.clone(), theme.style_accent())));
        } else {
            for event in &msg.events {
                match event {
                    TuiEvent::Delta(s) => {
                        for line in s.split('\n') {
                            lines.push(Line::from(Span::raw(line.to_string())));
                        }
                    }
                    TuiEvent::Reasoning(s) => {
                        lines.push(Line::from(Span::styled(
                            format!("  {}", s),
                            theme.style_think(),
                        )));
                    }
                    TuiEvent::ToolStart { tool, args } => {
                        let label = if args.is_empty() {
                            format!("  ◈ {tool}")
                        } else {
                            format!("  ◈ {tool} ({args})")
                        };
                        lines.push(Line::from(Span::styled(label, theme.style_tool())));
                    }
                    TuiEvent::ToolDone { tool, result } => {
                        let preview = if result.is_empty() {
                            String::new()
                        } else {
                            format!(" — {}", result.chars().take(60).collect::<String>().replace('\n', " "))
                        };
                        lines.push(Line::from(Span::styled(
                            format!("  ✓ {tool}{preview}"),
                            theme.style_success(),
                        )));
                    }
                    TuiEvent::ToolError { tool, error } => {
                        lines.push(Line::from(Span::styled(
                            format!("  ✗ {tool}: {error}"),
                            theme.style_error(),
                        )));
                    }
                    _ => {}
                }
            }
        }
        lines.push(Line::from(""));
    }
    lines
}
