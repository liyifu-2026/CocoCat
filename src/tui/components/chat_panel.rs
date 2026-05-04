use ratatui::{
    layout::Rect,
    style::Style,
    text::{Line, Span},
    widgets::{Paragraph, Scrollbar, ScrollbarOrientation, ScrollbarState, Wrap},
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
    area_y: u16,
) {
    let lines = build_message_lines(messages, area.width as usize, theme, area_y);

    let available_height = area.height.max(1) as usize;
    let max_scroll = lines.len().saturating_sub(available_height);
    let scroll = if max_scroll == 0 { 0 } else { scroll_offset.min(max_scroll) };
    let start = scroll;
    let end = (start + available_height).min(lines.len());

    let visible: Vec<Line> = if start < lines.len() {
        lines[start..end].to_vec()
    } else {
        vec![]
    };

    let paragraph = Paragraph::new(visible).wrap(Wrap { trim: false });
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

fn build_message_lines(messages: &[ChatMessage], width: usize, theme: &Theme, area_y: u16) -> Vec<Line<'static>> {
    let mut lines = Vec::new();
    let sep = "─".repeat(width.min(80));

    for msg in messages {
        if msg.role == "user" {
            let mut l = Line::from(Span::styled(sep.clone(), Style::default().fg(theme.text_dim_color())));
            lines.push(l);
            let mut l = Line::from(vec![
                Span::styled("┃ ", Style::default().fg(theme.accent_color())),
                Span::styled(msg.timestamp.clone(), Style::default().fg(theme.text_dim_color())),
            ]);
            lines.push(l);
            for content_line in msg.content.lines() {
                let mut l = Line::from(vec![
                    Span::styled("┃ ", Style::default().fg(theme.accent_color())),
                    Span::styled(content_line.to_string(), Style::default().fg(theme.text_color())),
                ]);
                lines.push(l);
            }
        } else {
            for event in &msg.events {
                match event {
                    TuiEvent::Delta(s) => {
                        let spans = crate::components::markdown::render_markdown(s, theme);
                        if spans.is_empty() {
                            for line in s.split('\n') {
                                let mut l = Line::from(Span::raw(line.to_string()));
                                lines.push(l);
                            }
                        } else {
                            let mut current_line = Vec::new();
                            for span in spans {
                                let text = span.content.to_string();
                                if text == "\n" {
                                    let mut l = Line::from(std::mem::take(&mut current_line));
                                    lines.push(l);
                                } else {
                                    current_line.push(span.clone());
                                }
                            }
                            if !current_line.is_empty() {
                                let mut l = Line::from(current_line);
                                lines.push(l);
                            }
                        }
                    }
                    TuiEvent::Reasoning(s) => {
                        let mut l = Line::from(Span::styled(format!(" _Thinking... {}", s), theme.style_think()));
                        lines.push(l);
                    }
                    TuiEvent::ToolStart { tool, args } => {
                        let label = if args.is_empty() { format!("  ◈ {tool}") } else { format!("  ◈ {tool} ({args})") };
                        let mut l = Line::from(Span::styled(label, theme.style_tool()));
                        lines.push(l);
                    }
                    TuiEvent::ToolDone { tool, result } => {
                        let preview = if result.is_empty() { String::new() } else {
                            format!(" — {}", result.chars().take(60).collect::<String>().replace('\n', " "))
                        };
                        let mut l = Line::from(Span::styled(format!("  ✓ {tool}{preview}"), theme.style_success()));
                        lines.push(l);
                    }
                    TuiEvent::ToolError { tool, error } => {
                        let mut l = Line::from(Span::styled(format!("  ✗ {tool}: {error}"), theme.style_error()));
                        lines.push(l);
                    }
                    _ => {}
                }
            }
            if !msg.is_streaming && msg.role == "assistant" {
                let mut l = Line::from(Span::styled(format!("  ▣ Build · {} · {:.1}s", "gpt-4", 0.0), Style::default().fg(theme.text_dim_color())));
                lines.push(l);
            }
        }
        let mut l = Line::from("");
        lines.push(l);
    }
    lines
}
