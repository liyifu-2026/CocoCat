use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Style},
    text::{Line, Span, Text},
    widgets::{Block, Borders, Paragraph},
    Frame,
};
use crate::theme::theme::Theme;

const BLOCK_BG: Color = Color::Rgb(0x2a, 0x2a, 0x2a);

pub struct InputBuffer {
    text: String,
    cursor: usize,
}

impl InputBuffer {
    pub fn new() -> Self {
        InputBuffer {
            text: String::new(),
            cursor: 0,
        }
    }

    pub fn text(&self) -> &str {
        &self.text
    }

    pub fn cursor(&self) -> usize {
        self.cursor
    }

    pub fn insert_char(&mut self, c: char) {
        self.text.insert(self.cursor, c);
        self.cursor += 1;
    }

    pub fn backspace(&mut self) {
        if self.cursor > 0 {
            self.cursor -= 1;
            self.text.remove(self.cursor);
        }
    }

    pub fn delete(&mut self) {
        if self.cursor < self.text.len() {
            self.text.remove(self.cursor);
        }
    }

    pub fn cursor_left(&mut self) {
        self.cursor = self.cursor.saturating_sub(1);
    }

    pub fn cursor_right(&mut self) {
        if self.cursor < self.text.len() {
            self.cursor += 1;
        }
    }

    pub fn set_text(&mut self, s: &str) {
        self.text = s.to_string();
        self.cursor = self.text.len();
    }

    pub fn clear(&mut self) {
        self.text.clear();
        self.cursor = 0;
    }

    pub fn take(&mut self) -> String {
        let s = self.text.clone();
        self.text.clear();
        self.cursor = 0;
        s
    }
}

pub struct InputHistory {
    entries: Vec<String>,
    index: Option<usize>,
    max: usize,
}

impl InputHistory {
    pub fn new(max: usize) -> Self {
        InputHistory {
            entries: Vec::new(),
            index: None,
            max,
        }
    }

    pub fn push(&mut self, s: String) {
        if s.is_empty() {
            return;
        }
        if self.entries.last().map(|e| e == &s).unwrap_or(false) {
            return;
        }
        self.entries.push(s);
        if self.entries.len() > self.max {
            self.entries.remove(0);
        }
        self.index = None;
    }

    pub fn navigate_prev(&mut self) -> Option<&str> {
        match self.index {
            None => {
                if self.entries.is_empty() {
                    return None;
                }
                self.index = Some(self.entries.len() - 1);
            }
            Some(i) => {
                if i == 0 {
                    return None;
                }
                self.index = Some(i - 1);
            }
        }
        self.index.and_then(|i| self.entries.get(i)).map(|s| s.as_str())
    }

    pub fn navigate_next(&mut self) -> Option<&str> {
        match self.index {
            None => None,
            Some(i) => {
                if i + 1 >= self.entries.len() {
                    self.index = None;
                    None
                } else {
                    self.index = Some(i + 1);
                    self.entries.get(i + 1).map(|s| s.as_str())
                }
            }
        }
    }

    pub fn reset_index(&mut self) {
        self.index = None;
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }
}

pub fn render_input_bar(
    f: &mut Frame, area: Rect, input: &InputBuffer,
    theme: &Theme, is_focused: bool, is_streaming: bool,
    agent_name: &str, model: &str, token_count: u32,
) {
    let block = Block::default()
        .borders(Borders::LEFT)
        .border_style(Style::default().fg(theme.accent_color()))
        .style(Style::default().bg(BLOCK_BG));

    let inner = block.inner(area);

    let chunks = Layout::default().direction(Direction::Vertical)
        .constraints([Constraint::Length(1), Constraint::Length(1)])
        .split(inner);

    let text = Paragraph::new(Text::from(Line::from(Span::raw(format!("> {}", input.text())))))
        .style(Style::default().fg(theme.text_color()));
    f.render_widget(text, chunks[0]);

    let mut meta = format!(" {} · {} · {} · {}K", agent_name, model, theme.name, token_count / 1000);
    if is_streaming {
        let spinner_chars = ['◌', '◯', '●', '○'];
        let frame = (std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH).unwrap_or_default()
            .as_millis() as usize / 150) % 4;
        meta.push(' ');
        meta.push(spinner_chars[frame]);
    }
    let meta = Paragraph::new(Text::from(Line::from(Span::styled(meta, Style::default().fg(theme.text_dim_color())))));
    f.render_widget(meta, chunks[1]);

    f.render_widget(block, area);
}
