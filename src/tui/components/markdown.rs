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

fn process_line_heading(line: &str) -> Option<(usize, &str)> {
    let trimmed = line.trim_start();
    let mut level = 0;
    for c in trimmed.chars() {
        if c == '#' { level += 1; } else { break; }
    }
    if level > 0 && level <= 6 && trimmed.len() > level && trimmed.chars().nth(level) == Some(' ') {
        Some((level, &trimmed[level + 1..]))
    } else {
        None
    }
}

fn line_is_unordered(line: &str) -> bool {
    let trimmed = line.trim_start();
    trimmed.starts_with("- ") || trimmed.starts_with("* ")
}

fn line_is_blockquote(line: &str) -> bool {
    let trimmed = line.trim_start();
    trimmed.starts_with("> ")
}

fn line_is_hr(line: &str) -> bool {
    let trimmed = line.trim();
    trimmed.len() >= 3 && trimmed.chars().all(|c| c == '-')
}

fn render_code_block(
    spans: &mut Vec<Span<'static>>,
    lines: &[String],
    lang: &str,
    ss: &SyntaxSet,
    syn_ts: &ThemeSet,
    theme_name: &str,
) {
    let lang = if lang.is_empty() { "text" } else { lang };
    let syntax = ss.find_syntax_by_token(lang).unwrap_or_else(|| ss.find_syntax_plain_text());
    let mut highlighter = HighlightLines::new(syntax, &syn_ts.themes[syntect_theme_name(theme_name)]);
    for line in lines {
        if let Ok(ranges) = highlighter.highlight_line(line, ss) {
            for (syn_style, text) in ranges {
                let fg = syn_style.foreground;
                let color = Color::Rgb(fg.r, fg.g, fg.b);
                spans.push(Span::styled(text.to_string(), Style::default().fg(color)));
            }
        }
        spans.push(Span::raw("\n"));
    }
}

fn render_inline(text: &str, theme: &Theme) -> Vec<Span<'static>> {
    let mut spans = Vec::new();
    let mut buf = String::new();
    let mut bold = false;
    let mut italic = false;
    let mut code = false;

    let chars: Vec<char> = text.chars().collect();
    let mut i = 0;

    while i < chars.len() {
        let c = chars[i];

        if c == '`' {
            flush(&mut spans, &mut buf, bold, italic, false, theme);
            code = !code;
            i += 1;
        } else if c == '[' && !code {
            let remaining = &chars[i..];
            if let Some(close_bracket) = remaining.iter().position(|&ch| ch == ']') {
                let after_bracket = i + close_bracket + 1;
                if after_bracket < chars.len() && chars[after_bracket] == '(' {
                    if let Some(close_paren) = chars[after_bracket..].iter().position(|&ch| ch == ')') {
                        let link_text: String = chars[i + 1..i + close_bracket].iter().collect();
                        flush(&mut spans, &mut buf, bold, italic, false, theme);
                        spans.push(Span::styled(
                            link_text,
                            Style::default().fg(theme.accent_color()).add_modifier(Modifier::UNDERLINED),
                        ));
                        i = after_bracket + close_paren + 1;
                        continue;
                    }
                }
            }
            buf.push(c);
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
        } else {
            buf.push(c);
            i += 1;
        }
    }

    flush(&mut spans, &mut buf, bold, italic, code, theme);
    spans
}

pub fn render_markdown(text: &str, theme: &Theme, theme_name: &str) -> Vec<Span<'static>> {
    let mut spans = Vec::new();
    let ss = get_syntax_set();
    let syn_ts = get_theme_set();

    let lines: Vec<&str> = text.lines().collect();
    let mut i = 0;
    let mut in_code_block = false;
    let mut code_block_lines: Vec<String> = Vec::new();
    let mut code_block_lang = String::new();

    while i < lines.len() {
        let raw_line = lines[i];

        if !in_code_block && raw_line.trim_start().starts_with("```") {
            in_code_block = true;
            code_block_lang = raw_line.trim_start().trim_start_matches('`').trim().to_string();
            code_block_lines.clear();
            i += 1;
            continue;
        }

        if in_code_block {
            if raw_line.trim_start().starts_with("```") {
                in_code_block = false;
                render_code_block(&mut spans, &code_block_lines, &code_block_lang, &ss, &syn_ts, theme_name);
                i += 1;
                continue;
            }
            code_block_lines.push(raw_line.to_string());
            i += 1;
            continue;
        }

        if line_is_hr(raw_line) {
            let count = raw_line.trim().chars().filter(|&c| c == '-').count();
            spans.push(Span::styled(
                "─".repeat(count),
                Style::default().fg(theme.text_color()).add_modifier(Modifier::DIM),
            ));
            spans.push(Span::raw("\n"));
            i += 1;
            continue;
        }

        if let Some((_level, heading_text)) = process_line_heading(raw_line) {
            spans.push(Span::styled(
                heading_text.to_string(),
                Style::default().fg(theme.accent_color()).add_modifier(Modifier::BOLD),
            ));
            spans.push(Span::raw("\n"));
            i += 1;
            continue;
        }

        if line_is_blockquote(raw_line) {
            let trimmed = raw_line.trim_start();
            let content = trimmed.strip_prefix("> ").unwrap_or(trimmed);
            spans.push(Span::styled(
                "▌ ",
                Style::default().fg(theme.text_color()).add_modifier(Modifier::DIM),
            ));
            let inline_spans = render_inline(content, theme);
            spans.extend(inline_spans);
            spans.push(Span::raw("\n"));
            i += 1;
            continue;
        }

        if line_is_unordered(raw_line) {
            let trimmed = raw_line.trim_start();
            let content = trimmed.strip_prefix("- ").or_else(|| trimmed.strip_prefix("* ")).unwrap_or(trimmed);
            let processed = format!("• {}", content);
            let inline_spans = render_inline(&processed, theme);
            spans.extend(inline_spans);
            spans.push(Span::raw("\n"));
            i += 1;
            continue;
        }

        let inline_spans = render_inline(raw_line, theme);
        spans.extend(inline_spans);
        spans.push(Span::raw("\n"));
        i += 1;
    }

    if in_code_block {
        render_code_block(&mut spans, &code_block_lines, &code_block_lang, &ss, &syn_ts, theme_name);
    } else if !text.ends_with('\n') {
        spans.pop();
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
