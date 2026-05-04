use std::sync::OnceLock;
use ratatui::style::{Style, Modifier, Color};
use ratatui::text::Span;
use syntect::parsing::SyntaxSet;
use syntect::highlighting::ThemeSet;
use syntect::easy::HighlightLines;
use crate::theme::theme::Theme;

fn syntect_theme_name(app_theme_name: &str) -> &str {
    match app_theme_name {
        "catppuccin-mocha" => "base16-mocha.dark",
        "nord" => "base16-nord",
        "dracula" => "base16-dracula",
        "tokyonight" => "base16-tokyo-night",
        "gruvbox" => "base16-gruvbox.dark",
        _ => "base16-ocean.dark",
    }
}

fn get_syntax_set() -> &'static SyntaxSet {
    static SS: OnceLock<SyntaxSet> = OnceLock::new();
    SS.get_or_init(|| SyntaxSet::load_defaults_newlines())
}

fn get_theme_set() -> &'static ThemeSet {
    static TS: OnceLock<ThemeSet> = OnceLock::new();
    TS.get_or_init(|| ThemeSet::load_defaults())
}

pub fn render_markdown(text: &str, theme: &Theme, theme_name: &str) -> Vec<Span<'static>> {
    let mut spans = Vec::new();
    let mut buf = String::new();
    let mut bold = false;
    let mut italic = false;
    let mut code = false;
    let mut code_block = false;
    let mut code_block_lang = String::new();

    let ss = get_syntax_set();
    let syn_ts = get_theme_set();

    let chars: Vec<char> = text.chars().collect();
    let mut i = 0;

    while i < chars.len() {
        let c = chars[i];

        if !code && i + 2 < chars.len() && c == '`' && chars[i+1] == '`' && chars[i+2] == '`' {
            if code_block {
                let lang = if code_block_lang.is_empty() { "text" } else { &code_block_lang };
                let syntax = ss.find_syntax_by_token(lang).unwrap_or_else(|| ss.find_syntax_plain_text());
                let mut highlighter = HighlightLines::new(syntax, &syn_ts.themes[syntect_theme_name(theme_name)]);
                for line in buf.lines() {
                    if let Ok(ranges) = highlighter.highlight_line(line, ss) {
                        for (syn_style, text) in ranges {
                            let fg = syn_style.foreground;
                            let color = Color::Rgb(fg.r, fg.g, fg.b);
                            spans.push(Span::styled(text.to_string(), Style::default().fg(color)));
                        }
                    }
                    spans.push(Span::raw("\n"));
                }
                buf.clear();
            } else {
                flush(&mut spans, &mut buf, bold, italic, false, theme);
            }
            code_block = !code_block;
            if code_block {
                let mut j = i + 3;
                code_block_lang.clear();
                while j < chars.len() && chars[j] != '\n' && chars[j] != '`' {
                    code_block_lang.push(chars[j]);
                    j += 1;
                }
                i = j;
            } else {
                i += 3;
            }
            continue;
        }

        if code_block {
            buf.push(c);
            i += 1;
            continue;
        }

        if c == '`' {
            flush(&mut spans, &mut buf, bold, italic, false, theme);
            code = !code;
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

    if code_block {
        let lang = if code_block_lang.is_empty() { "text" } else { &code_block_lang };
        let syntax = ss.find_syntax_by_token(lang).unwrap_or_else(|| ss.find_syntax_plain_text());
        let mut highlighter = HighlightLines::new(syntax, &syn_ts.themes[syntect_theme_name(theme_name)]);
        for line in buf.lines() {
            if let Ok(ranges) = highlighter.highlight_line(line, ss) {
                for (syn_style, text) in ranges {
                    let fg = syn_style.foreground;
                    let color = Color::Rgb(fg.r, fg.g, fg.b);
                    spans.push(Span::styled(text.to_string(), Style::default().fg(color)));
                }
            }
            spans.push(Span::raw("\n"));
        }
    } else {
        flush(&mut spans, &mut buf, bold, italic, code, theme);
    }

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
