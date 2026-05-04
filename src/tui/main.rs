use std::io::{self, Write};
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::sync::mpsc;
use std::time::Duration;

use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Style},
    widgets::{Block, Clear},
    Terminal,
};
use crossterm::{
    event::{self as crossterm_event, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind, KeyModifiers, MouseButton, MouseEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};

mod app;
mod components;
mod config;
mod event;
mod protocol;
mod session;
mod theme;
mod types;

use app::{App, Dialog};
use event::TuiEvent;
use protocol::client::AgentClient;
use components::{autocomplete, chat_panel, dialogs, header, input_bar, reply_dialog, sidebar, status_bar};
use components::autocomplete::AutocompleteState;
use components::input_bar::{InputBuffer, InputHistory};
use components::reply_dialog::ReplyDialog;

struct Cleanup;

impl Drop for Cleanup {
    fn drop(&mut self) {
        let _ = disable_raw_mode();
        let _ = execute!(io::stdout(), LeaveAlternateScreen, DisableMouseCapture);
    }
}

fn report_error(msg: &str) {
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true).append(true).open(
            dirs::home_dir().unwrap_or_default().join(".cococat/crash.log")
        ) {
        let _ = writeln!(f, "CocoCat TUI crash: {}", msg);
    }
    let _ = writeln!(io::stderr(), "\nCocoCat TUI crash: {}\n", msg);
    let _ = write!(io::stderr(), "Press Enter to exit...");
    let _ = io::stdin().read_line(&mut String::new());
}

fn handle_key(
    key: KeyCode,
    modifiers: KeyModifiers,
    app: &mut App,
    autocomplete: &mut AutocompleteState,
    reply_dialog: &mut ReplyDialog,
    input: &mut InputBuffer,
    history: &mut InputHistory,
    agent_client: &mut AgentClient,
    tx: &mpsc::Sender<TuiEvent>,
    is_streaming: &mut bool,
) {
    if autocomplete.visible {
        match (key, modifiers) {
            (KeyCode::Up, _) => { autocomplete.previous(); return; }
            (KeyCode::Down, _) => { autocomplete.next(); return; }
            (KeyCode::Enter, _) => {
                if let Some(cmd) = autocomplete.selected_command() {
                    input.set_text(&cmd);
                    input.insert_char(' ');
                }
                autocomplete.reset();
                return;
            }
            (KeyCode::Esc, _) => { autocomplete.reset(); return; }
            (KeyCode::Backspace, _) => { input.backspace(); if input.text().starts_with('/') { autocomplete.filter(input.text()); } else { autocomplete.reset(); } return; }
            (KeyCode::Char(c), _) => { input.insert_char(c); autocomplete.filter(input.text()); return; }
            _ => {}
        }
    }

    if reply_dialog.visible {
        match (key, modifiers) {
            (KeyCode::Esc, _) => { reply_dialog.close(); return; }
            (KeyCode::Enter, _) => { reply_dialog.close(); return; }
            (KeyCode::Char(c), _) => { reply_dialog.insert_char(c); return; }
            (KeyCode::Backspace, _) => { reply_dialog.backspace(); return; }
            _ => return,
        }
    }

    if app.dialog.is_some() {
        match key {
            KeyCode::Esc => app.dialog = None,
            KeyCode::Enter => app.dialog = None,
            _ => {}
        }
        return;
    }

    match (key, modifiers) {
        (KeyCode::Char('q'), KeyModifiers::CONTROL) | (KeyCode::Char('c'), KeyModifiers::CONTROL) => {
            agent_client.close();
            app.quit();
        }
        (KeyCode::Char('b'), KeyModifiers::CONTROL) => { app.toggle_sidebar(); }
        (KeyCode::Tab, _) => {
            if let Some(section) = app.sidebar_sections.get_mut(0) { section.toggle(); }
        }
        (KeyCode::Char('p'), KeyModifiers::CONTROL) => { app.dialog = Some(Dialog::SessionSwitcher); }
        (KeyCode::Esc, _) => { app.dialog = None; }
        (KeyCode::Enter, _) => {
            if *is_streaming { return; }
            let text = input.take();
            if text.is_empty() { return; }
            if text.starts_with('/') {
                handle_slash_command(&text, app, input, history);
                return;
            }
            app.add_user_message(text.clone());
            history.push(text.clone());
            app.start_assistant_message();
            *is_streaming = true;
            if let Err(e) = agent_client.send_stream(&app.agent_id, &text, tx.clone()) {
                app.finalize_last_message();
                *is_streaming = false;
                app.status_message = format!("Error: {}", e);
            }
        }
        (KeyCode::Char(c), _) => {
            if c == '/' && input.cursor() == 0 { autocomplete.trigger(); }
            input.insert_char(c);
        }
        (KeyCode::Backspace, _) => { input.backspace(); }
        (KeyCode::Delete, _) => { input.delete(); }
        (KeyCode::Left, _) => { input.cursor_left(); }
        (KeyCode::Right, _) => { input.cursor_right(); }
        (KeyCode::Up, _) => {
            if let Some(s) = history.navigate_prev() { input.set_text(s); }
        }
        (KeyCode::Down, _) => {
            if let Some(s) = history.navigate_next() { input.set_text(s); }
            else { input.clear(); }
        }
        _ => {}
    }
}

fn handle_slash_command(text: &str, app: &mut App, input: &mut InputBuffer, history: &mut InputHistory) {
    let parts: Vec<&str> = text.splitn(2, ' ').collect();
    let cmd = parts[0].to_lowercase();
    match cmd.as_str() {
        "/theme" => {
            if let Some(name) = parts.get(1) {
                let name = name.trim();
                if app.switch_theme(name) { app.status_message = format!("Switched to theme: {}", name); }
                else { app.status_message = format!("Unknown theme: {}", name); }
            } else { app.dialog = Some(Dialog::ThemeSelector); }
        }
        "/help" | "/?" => { app.dialog = Some(Dialog::Help); }
        "/clear" => { app.messages.clear(); app.scroll_to_bottom(); }
        "/model" => { app.dialog = Some(Dialog::ModelSelector); }
        "/session" => { app.dialog = Some(Dialog::SessionSwitcher); }
        "/quit" => { app.quit(); }
        _ => { app.status_message = format!("Unknown command: {}", cmd); }
    }
    input.clear();
    history.push(text.to_string());
}

fn process_sidebar_click(app: &mut App, col: i32, row: i32, term_width: u16) {
    let sidebar_visible = app.show_sidebar || (app.sidebar_auto && term_width > 120);
    let sidebar_x = (term_width as i32).saturating_sub(42);
    if !sidebar_visible || col < sidebar_x || col >= term_width as i32 { return; }
    let content_row = row.saturating_sub(1);
    let mut current_row = 0i32;
    for section in app.sidebar_sections.iter_mut() {
        if content_row == current_row { section.collapsed = !section.collapsed; return; }
        current_row += 1;
        if !section.collapsed {
            match section.name.as_str() {
                "Team" => { current_row += 4; }
                "Session" => { current_row += 3; }
                "Tools" => { current_row += app.tool_stats.tool_calls.len().max(1) as i32; }
                "Mail" => { current_row += 2; }
                _ => {}
            }
        }
        current_row += 1;
    }
}

fn run_tui() -> io::Result<()> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.hide_cursor()?;

    let _guard = Cleanup;

    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    if let Err(e) = ctrlc::set_handler(move || { r.store(false, Ordering::Relaxed); }) {
        eprintln!("Warning: could not set Ctrl+C handler: {e}");
    }

    let cfg = config::Config::load_or_default(config::Config::config_path()).unwrap_or_default();
    let agent_id = std::env::args().nth(1).unwrap_or_else(|| cfg.chat.default_agent.clone());
    let mut app = App::new(&agent_id);
    app.agent_statuses = vec![
        app::AgentStatus { id: "leader".into(), name: "Leader".into(), running: true },
        app::AgentStatus { id: "emp_a".into(), name: "Emp A".into(), running: true },
        app::AgentStatus { id: "emp_b".into(), name: "Emp B".into(), running: false },
        app::AgentStatus { id: "emp_c".into(), name: "Emp C".into(), running: false },
    ];
    let mut input = InputBuffer::new();
    let mut history = InputHistory::new(200);
    let mut agent_client = AgentClient::new(".");
    let (tx, rx) = mpsc::channel::<TuiEvent>();
    let mut is_streaming = false;
    let mut autocomplete = AutocompleteState::new();
    let mut reply_dialog = ReplyDialog::new();
    let mut pending_click: Option<(i32, i32)> = None;
    let mut hovered_row: Option<u16> = None;

    while running.load(Ordering::Relaxed) && !app.should_quit {
        terminal.draw(|f| {
            let area = f.area();
            let term_width = area.width;
            let sidebar_visible = app.show_sidebar || (app.sidebar_auto && term_width > 120);

            let chunks = if sidebar_visible && term_width > 120 {
                Layout::default().direction(Direction::Horizontal)
                    .constraints([Constraint::Min(0), Constraint::Length(42)]).split(area)
            } else {
                Layout::default().direction(Direction::Horizontal)
                    .constraints([Constraint::Percentage(100), Constraint::Length(0)]).split(area)
            };

            let vertical = Layout::default().direction(Direction::Vertical)
                .constraints([
                    Constraint::Length(1), Constraint::Length(1),
                    Constraint::Min(3), Constraint::Length(1),
                    Constraint::Length(3), Constraint::Length(1),
                    Constraint::Length(1),
                ]).split(chunks[0]);

            header::render_header(f, vertical[0], &app.agent_id, app.theme_registry.current_theme());
            chat_panel::render_chat_panel(f, vertical[2], &app.messages, app.scroll_offset, app.theme_registry.current_theme(), true, hovered_row, vertical[2].y);
            input_bar::render_input_bar(f, vertical[4], &input, app.theme_registry.current_theme(), !is_streaming, is_streaming, &app.agent_id, "gpt-4", app.session_stats.token_count);
            status_bar::render_status_bar(f, vertical[6], &app.agent_id, "default", app.theme_registry.current_theme());

            if sidebar_visible && term_width > 120 {
                sidebar::render_sidebar(f, chunks[1], &mut app.sidebar_sections, &app.tool_stats, &app.session_stats, &app.system_stats, app.theme_registry.current_theme());
            }

            if app.show_sidebar && term_width <= 120 {
                let overlay = Layout::default().direction(Direction::Horizontal)
                    .constraints([Constraint::Min(0), Constraint::Length(42)]).split(area);
                f.render_widget(Clear, area);
                f.render_widget(Block::default().style(Style::default().bg(Color::Rgb(0, 0, 0)).fg(Color::Rgb(0, 0, 0))), area);
                sidebar::render_sidebar(f, overlay[1], &mut app.sidebar_sections, &app.tool_stats, &app.session_stats, &app.system_stats, app.theme_registry.current_theme());
            }

            if let Some(ref dialog) = app.dialog { dialogs::render_dialog(f, area, dialog, &app); }
            if autocomplete.visible { autocomplete::render_autocomplete(f, vertical[4], &autocomplete, app.theme_registry.current_theme()); }
            if reply_dialog.visible { reply_dialog::render_reply_dialog(f, area, &reply_dialog, app.theme_registry.current_theme()); }
        })?;

        if crossterm_event::poll(Duration::from_millis(100))? {
            match crossterm_event::read()? {
                Event::Key(key) => {
                    if key.kind == KeyEventKind::Press {
                        handle_key(key.code, key.modifiers, &mut app, &mut autocomplete, &mut reply_dialog, &mut input, &mut history, &mut agent_client, &tx, &mut is_streaming);
                    }
                }
                Event::Mouse(mouse) => {
                    if mouse.kind == MouseEventKind::Down(MouseButton::Left) {
                        pending_click = Some((mouse.column as i32, mouse.row as i32));
                    }
                }
                _ => {}
            }
        }

        if let Some((col, row)) = pending_click.take() {
            if let Ok(size) = terminal.size() { process_sidebar_click(&mut app, col, row, size.width); }
        }

        if is_streaming {
            while let Ok(event) = rx.try_recv() {
                match event {
                    TuiEvent::ToolStart { tool, .. } => app.track_tool_start(&tool),
                    TuiEvent::ToolDone { tool, .. } => app.track_tool_done(&tool),
                    TuiEvent::ToolError { tool, .. } => app.track_tool_error(&tool),
                    TuiEvent::Done(_) | TuiEvent::JsonRpcDone(_) => {
                        app.finalize_last_message();
                        app.session_stats.message_count = app.messages.len();
                        app.session_stats.agent_name = app.agent_id.clone();
                        is_streaming = false;
                    }
                    TuiEvent::JsonRpcError(_) => { app.finalize_last_message(); is_streaming = false; }
                    e => { app.append_to_last(e); }
                }
            }
        }
    }

    agent_client.close();
    Ok(())
}

fn main() {
    match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> io::Result<()> {
        let result = run_tui();
        if let Err(ref e) = result {
            // Print error BEFORE Cleanup restores terminal
            report_error(&format!("TUI error: {}", e));
        }
        result
    })) {
        Ok(Ok(())) => {}
        Ok(Err(_)) => {} // error already reported above
        Err(panic) => {
            let msg = if let Some(s) = panic.downcast_ref::<&str>() { s.to_string() }
                      else if let Some(s) = panic.downcast_ref::<String>() { s.clone() }
                      else { "unknown panic".to_string() };
            report_error(&format!("PANIC: {}", msg));
        }
    }
}
