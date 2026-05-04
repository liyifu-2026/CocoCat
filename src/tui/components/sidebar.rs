use ratatui::{
    layout::Rect,
    style::{Color, Style},
    text::{Line, Span, Text},
    widgets::{Block, Paragraph, Wrap},
    Frame,
};
use crate::app::SidebarSection;
use crate::theme::theme::Theme;
use crate::types::stats::{ToolStats, SessionStats, SystemStats};

const BLOCK_BG: Color = Color::Rgb(0x2a, 0x2a, 0x2a);

pub fn render_sidebar(
    f: &mut Frame, area: Rect, sections: &mut [SidebarSection],
    tool_stats: &ToolStats, session_stats: &SessionStats, system_stats: &SystemStats,
    theme: &Theme,
) {
    let block = Block::default()
        .style(Style::default().bg(BLOCK_BG));

    let mut lines: Vec<Line> = Vec::new();

    for section in sections.iter() {
        match section.name.as_str() {
            "Team" => render_team_section(&mut lines, section, theme),
            "Session" => render_session_section(&mut lines, section, session_stats, theme),
            "Tools" => render_tools_section(&mut lines, section, tool_stats, theme),
            "Mail" => render_mail_section(&mut lines, section, system_stats, theme),
            _ => {}
        }
        lines.push(Line::from(""));
    }

    lines.push(Line::from(Span::styled(" CocoCat v0.1.0", Style::default().fg(theme.text_dim_color()))));
    let theme_name = &theme.name;
    lines.push(Line::from(Span::styled(format!(" {}", theme_name), Style::default().fg(theme.text_dim_color()))));

    let paragraph = Paragraph::new(Text::from(lines)).block(block).wrap(Wrap { trim: false });
    f.render_widget(paragraph, area);
}

fn section_header(lines: &mut Vec<Line>, name: &str, collapsed: bool, theme: &Theme) {
    let icon = if collapsed { "▶" } else { "▼" };
    lines.push(Line::from(Span::styled(
        format!(" {} {}", icon, name),
        Style::default().fg(theme.accent_color()),
    )));
}

fn render_team_section(lines: &mut Vec<Line>, section: &SidebarSection, theme: &Theme) {
    section_header(lines, &section.name, section.collapsed, theme);
    if !section.collapsed {
        lines.push(Line::from(Span::styled("  4 agents", Style::default().fg(theme.text_color()))));
        lines.push(Line::from(Span::styled("  leader    ● running", Style::default().fg(theme.text_color()))));
        lines.push(Line::from(Span::styled("  emp_a     ● running", Style::default().fg(theme.text_color()))));
        lines.push(Line::from(Span::styled("  emp_b     ○ idle", Style::default().fg(theme.text_dim_color()))));
        lines.push(Line::from(Span::styled("  emp_c     ○ idle", Style::default().fg(theme.text_dim_color()))));
    }
}

fn render_session_section(lines: &mut Vec<Line>, section: &SidebarSection, stats: &SessionStats, theme: &Theme) {
    section_header(lines, &section.name, section.collapsed, theme);
    if !section.collapsed {
        lines.push(Line::from(Span::styled(format!("  Messages  {}", stats.message_count), Style::default().fg(theme.text_color()))));
        lines.push(Line::from(Span::styled(format!("  Tokens    {} / {}", stats.token_count, stats.token_limit), Style::default().fg(theme.text_color()))));
        lines.push(Line::from(Span::styled(format!("  Agent     {}", stats.agent_name), Style::default().fg(theme.text_color()))));
    }
}

fn render_tools_section(lines: &mut Vec<Line>, section: &SidebarSection, stats: &ToolStats, theme: &Theme) {
    section_header(lines, &section.name, section.collapsed, theme);
    if !section.collapsed {
        if stats.tool_calls.is_empty() {
            lines.push(Line::from(Span::styled("  (none yet)", Style::default().fg(theme.text_dim_color()))));
        } else {
            for tc in &stats.tool_calls {
                let icon = match tc.status.as_str() {
                    "done" => "✓",
                    "running" => "◌",
                    "error" => "✗",
                    _ => "?",
                };
                lines.push(Line::from(Span::styled(
                    format!("  {} {}  {}x", icon, tc.name, tc.count),
                    Style::default().fg(theme.text_color()),
                )));
            }
        }
    }
}

fn render_mail_section(lines: &mut Vec<Line>, section: &SidebarSection, stats: &SystemStats, theme: &Theme) {
    section_header(lines, &section.name, section.collapsed, theme);
    if !section.collapsed {
        lines.push(Line::from(Span::styled(format!("  {} unread", stats.unread_mail), Style::default().fg(theme.text_color()))));
        lines.push(Line::from(Span::styled(format!("  {} dispatches pending", stats.pending_dispatches), Style::default().fg(theme.text_color()))));
    }
}
