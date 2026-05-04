use ratatui::{
    layout::{Alignment, Rect, Constraint, Direction, Layout},
    style::Style,
    text::{Line, Span, Text},
    widgets::{Block, Borders, Clear, List, ListItem, Paragraph},
    Frame,
};
use crate::app::{App, Dialog};

pub fn centered_rect(percent_x: u16, percent_y: u16, r: Rect) -> Rect {
    let popup = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length((r.height * (100 - percent_y)) / 200),
            Constraint::Length((r.height * percent_y) / 100),
            Constraint::Length((r.height * (100 - percent_y)) / 200),
        ])
        .split(r);

    Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Length((r.width * (100 - percent_x)) / 200),
            Constraint::Length((r.width * percent_x) / 100),
            Constraint::Length((r.width * (100 - percent_x)) / 200),
        ])
        .split(popup[1])[1]
}

pub fn render_dialog(f: &mut Frame, area: Rect, dialog: &Dialog, app: &App) {
    match dialog {
        Dialog::ThemeSelector => render_theme_selector(f, area, app),
        Dialog::Help => render_help(f, area, app),
        Dialog::SessionSwitcher => render_session_switcher(f, area, app),
    }
}

fn render_theme_selector(f: &mut Frame, area: Rect, app: &App) {
    let theme = app.theme_registry.current_theme();
    let dialog_area = centered_rect(50, 50, area);

    let items: Vec<ListItem> = app.theme_registry.all().iter().map(|t| {
        let selected = t.name == app.theme_registry.current();
        let style = if selected {
            Style::default().fg(theme.accent_color())
        } else {
            Style::default().fg(theme.text_color())
        };
        let prefix = if selected { "▶ " } else { "  " };
        ListItem::new(Line::from(Span::styled(format!("{prefix}{}", t.name), style)))
    }).collect();

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.accent_color()))
        .title(Span::styled(" Select Theme ", Style::default().fg(theme.accent_color())))
        .style(Style::default().bg(theme.bg()));

    let list = List::new(items).block(block);
    f.render_widget(Clear, dialog_area);
    f.render_widget(list, dialog_area);
}

fn render_help(f: &mut Frame, area: Rect, app: &App) {
    let theme = app.theme_registry.current_theme();
    let dialog_area = centered_rect(60, 70, area);

    let help_lines = vec![
        Line::from(Span::styled("  Keyboard Shortcuts", Style::default().fg(theme.accent_color()))),
        Line::from(""),
        Line::from(Span::styled("  Ctrl+Q    Quit", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  Ctrl+B    Toggle sidebar", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  Tab       Cycle sidebar tab", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  Ctrl+P    Quick session switch", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  Esc       Close dialog", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  Enter     Send message", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  ↑↓        History navigation", Style::default().fg(theme.text_color()))),
        Line::from(""),
        Line::from(Span::styled("  Commands", Style::default().fg(theme.accent_color()))),
        Line::from(Span::styled("  /theme [name]  Switch theme", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  /clear         Clear chat", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  /help          Show this help", Style::default().fg(theme.text_color()))),
        Line::from(Span::styled("  /quit          Exit", Style::default().fg(theme.text_color()))),
        Line::from(""),
        Line::from(Span::styled("  Press any key to close", Style::default().fg(theme.text_dim_color()))),
    ];

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.accent_color()))
        .title(Span::styled(" Help ", Style::default().fg(theme.accent_color())))
        .style(Style::default().bg(theme.bg()));

    let paragraph = Paragraph::new(Text::from(help_lines))
        .block(block)
        .alignment(Alignment::Left);
    f.render_widget(Clear, dialog_area);
    f.render_widget(paragraph, dialog_area);
}

fn render_session_switcher(f: &mut Frame, area: Rect, app: &App) {
    let theme = app.theme_registry.current_theme();
    let dialog_area = centered_rect(50, 50, area);

    let items: Vec<ListItem> = vec![
        ListItem::new(Line::from(Span::styled("  Session list (coming soon)", Style::default().fg(theme.text_dim_color())))),
    ];

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.accent_color()))
        .title(Span::styled(" Sessions ", Style::default().fg(theme.accent_color())))
        .style(Style::default().bg(theme.bg()));

    let list = List::new(items).block(block);
    f.render_widget(Clear, dialog_area);
    f.render_widget(list, dialog_area);
}
