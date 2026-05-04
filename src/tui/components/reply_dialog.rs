use ratatui::{
    layout::{Rect, Alignment, Constraint, Direction, Layout},
    style::Style,
    text::{Line, Span, Text},
    widgets::{Block, Borders, Clear, Paragraph, Wrap},
    Frame,
};
use crate::theme::theme::Theme;

pub enum DialogType {
    MailReply { from: String, content: String },
    Dispatch { task: String, from: String },
}

pub struct ReplyDialog {
    pub visible: bool,
    pub dialog_type: Option<DialogType>,
    pub input: String,
    pub cursor: usize,
}

impl ReplyDialog {
    pub fn new() -> Self {
        ReplyDialog { visible: false, dialog_type: None, input: String::new(), cursor: 0 }
    }

    pub fn open_mail(&mut self, from: &str, content: &str) {
        self.visible = true;
        self.dialog_type = Some(DialogType::MailReply {
            from: from.to_string(), content: content.to_string(),
        });
        self.input.clear();
        self.cursor = 0;
    }

    pub fn open_dispatch(&mut self, task: &str, from: &str) {
        self.visible = true;
        self.dialog_type = Some(DialogType::Dispatch {
            task: task.to_string(), from: from.to_string(),
        });
        self.input.clear();
        self.cursor = 0;
    }

    pub fn close(&mut self) { self.visible = false; self.dialog_type = None; }

    pub fn insert_char(&mut self, c: char) {
        self.input.insert(self.cursor, c); self.cursor += 1;
    }
    pub fn backspace(&mut self) {
        if self.cursor > 0 { self.input.remove(self.cursor - 1); self.cursor -= 1; }
    }
}

pub fn render_reply_dialog(f: &mut Frame, area: Rect, dialog: &ReplyDialog, theme: &Theme) {
    if !dialog.visible { return; }

    let (title, body, _has_accept) = match &dialog.dialog_type {
        Some(DialogType::MailReply { from, content }) => {
            let body: String = content.lines().take(20).collect::<Vec<_>>().join("\n");
            (format!(" Reply to {} ", from), body, false)
        }
        Some(DialogType::Dispatch { task, from }) => {
            let body = format!("Task: {}\nFrom: {}", task, from);
            (format!(" Dispatch "), body, true)
        }
        None => return,
    };

    let dialog_area = centered_rect(60, 70, area);
    f.render_widget(Clear, dialog_area);

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.accent_color()))
        .title(Span::styled(title, Style::default().fg(theme.accent_color())));
    let inner = block.inner(dialog_area);

    let chunks = Layout::default().direction(Direction::Vertical)
        .constraints([
            Constraint::Min(1),
            Constraint::Length(1),
            Constraint::Length(3),
            Constraint::Length(1),
        ]).split(inner);

    let body_para = Paragraph::new(Text::from(body))
        .style(Style::default().fg(theme.text_color()))
        .wrap(Wrap { trim: false });
    f.render_widget(body_para, chunks[0]);

    let sep = Paragraph::new(Line::from(Span::styled(
        "─".repeat(chunks[1].width as usize),
        Style::default().fg(theme.text_dim_color()),
    )));
    f.render_widget(sep, chunks[1]);

    let input_para = Paragraph::new(Line::from(Span::styled(
        format!("> {}", dialog.input),
        Style::default().fg(theme.text_color()),
    )));
    f.render_widget(input_para, chunks[2]);

    let btn_text = "  [Enter: Send]  [Esc: Cancel]  ";
    let buttons = Paragraph::new(Line::from(Span::styled(btn_text, Style::default().fg(theme.text_dim_color()))))
        .alignment(Alignment::Center);
    f.render_widget(buttons, chunks[3]);

    f.render_widget(block, dialog_area);
}

fn centered_rect(percent_x: u16, percent_y: u16, r: Rect) -> Rect {
    let popup = Layout::default().direction(Direction::Vertical)
        .constraints([
            Constraint::Length((r.height * (100 - percent_y)) / 200),
            Constraint::Length((r.height * percent_y) / 100),
            Constraint::Length((r.height * (100 - percent_y)) / 200),
        ]).split(r);
    Layout::default().direction(Direction::Horizontal)
        .constraints([
            Constraint::Length((r.width * (100 - percent_x)) / 200),
            Constraint::Length((r.width * percent_x) / 100),
            Constraint::Length((r.width * (100 - percent_x)) / 200),
        ]).split(popup[1])[1]
}
