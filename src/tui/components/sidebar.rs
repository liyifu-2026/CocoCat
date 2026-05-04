use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::Style,
    text::{Line, Span, Text},
    widgets::{Block, Borders, List, ListItem, Paragraph, Tabs},
    Frame,
};
use crate::app::SidebarTab;
use crate::theme::theme::Theme;

pub fn next_tab(tab: &SidebarTab) -> SidebarTab {
    match tab {
        SidebarTab::Sessions => SidebarTab::Context,
        SidebarTab::Context => SidebarTab::Help,
        SidebarTab::Help => SidebarTab::Sessions,
    }
}

pub fn tab_name(tab: &SidebarTab) -> &'static str {
    match tab {
        SidebarTab::Sessions => "Sessions",
        SidebarTab::Context => "Context",
        SidebarTab::Help => "Help",
    }
}

pub fn render_sidebar(f: &mut Frame, area: Rect, tab: &SidebarTab, theme: &Theme) {
    let names = ["Sessions", "Context", "Help"];
    let selected = match tab {
        SidebarTab::Sessions => 0,
        SidebarTab::Context => 1,
        SidebarTab::Help => 2,
    };

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(3), Constraint::Min(0)])
        .split(area);

    let tabs = Tabs::new(names.to_vec())
    .select(selected)
    .highlight_style(Style::default().fg(theme.accent_color()))
    .block(Block::default().title(" Sidebar ").borders(Borders::ALL));

    f.render_widget(tabs, chunks[0]);

    let content_block = Block::default().borders(Borders::ALL);

    match tab {
        SidebarTab::Sessions => {
            let items = vec![ListItem::new("No sessions yet")];
            let list = List::new(items).block(content_block);
            f.render_widget(list, chunks[1]);
        }
        SidebarTab::Context => {
            let text = Text::from(vec![
                Line::from(Span::raw("Tokens: --")),
                Line::from(Span::raw("Tools: --")),
            ]);
            let paragraph = Paragraph::new(text).block(content_block);
            f.render_widget(paragraph, chunks[1]);
        }
        SidebarTab::Help => {
            let help_lines = vec![
                ListItem::new("Ctrl+Q / Ctrl+C  Quit"),
                ListItem::new("Ctrl+B           Toggle sidebar"),
                ListItem::new("Tab              Cycle sidebar tab"),
                ListItem::new("Ctrl+P           Session switcher"),
                ListItem::new("Esc              Close dialog"),
                ListItem::new("Enter            Send message"),
                ListItem::new("↑↓               History navigation"),
                ListItem::new("←→               Cursor move"),
                ListItem::new("/theme [name]    Switch theme"),
                ListItem::new("/help            Show help"),
                ListItem::new("/clear           Clear chat"),
                ListItem::new("/quit            Exit"),
            ];
            let list = List::new(help_lines).block(content_block);
            f.render_widget(list, chunks[1]);
        }
    }
}
