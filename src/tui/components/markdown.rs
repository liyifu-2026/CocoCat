use ratatui::style::{Style, Modifier};
use ratatui::text::Span;
use crate::theme::theme::Theme;

pub fn render_markdown(text: &str, theme: &Theme) -> Vec<Span<'static>> {
    let mut spans = Vec::new();
    let mut buf = String::new();
    let mut bold = false;
    let mut italic = false;
    let mut code = false;

    let chars: Vec<char> = text.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];

        if c == '`' && !code {
            flush(&mut spans, &mut buf, bold, italic, false, theme);
            code = true;
            i += 1;
        } else if c == '`' && code {
            flush(&mut spans, &mut buf, bold, italic, true, theme);
            code = false;
            i += 1;
        } else if c == '*' && !code {
            if i + 1 < chars.len() && chars[i + 1] == '*' {
                flush(&mut spans, &mut buf, bold, italic, false, theme);
                bold = !bold;
                i += 2;
            } else {
                flush(&mut spans, &mut buf, bold, italic, false, theme);
                italic = !italic;
                i += 1;
            }
        } else if c == '\n' {
            flush(&mut spans, &mut buf, bold, italic, code, theme);
            spans.push(Span::raw("\n"));
            i += 1;
        } else {
            buf.push(c);
            i += 1;
        }
    }
    flush(&mut spans, &mut buf, bold, italic, code, theme);
    spans
}

fn flush(spans: &mut Vec<Span<'static>>, buf: &mut String, bold: bool, italic: bool, code: bool, theme: &Theme) {
    if buf.is_empty() { return; }
    let mut style = if code {
        Style::default().fg(theme.accent_color())
    } else {
        Style::default().fg(theme.text_color())
    };
    if bold { style = style.add_modifier(Modifier::BOLD); }
    if italic { style = style.add_modifier(Modifier::ITALIC); }
    spans.push(Span::styled(std::mem::take(buf), style));
}
