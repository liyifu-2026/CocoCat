use std::io;
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
    event::{self as crossterm_event, Event, KeyCode, KeyEventKind, KeyModifiers},
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
use components::{chat_panel, dialogs, header, input_bar, sidebar, status_bar};
use components::input_bar::{InputBuffer, InputHistory};

struct Cleanup;

impl Drop for Cleanup {
    fn drop(&mut self) {
        let _ = disable_raw_mode();
        let _ = execute!(io::stdout(), LeaveAlternateScreen);
    }
}

fn handle_key(
    key: KeyCode,
    modifiers: KeyModifiers,
    app: &mut App,
    input: &mut InputBuffer,
    history: &mut InputHistory,
    agent_client: &mut AgentClient,
    tx: &mpsc::Sender<TuiEvent>,
    is_streaming: &mut bool,
) {
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
        (KeyCode::Char('b'), KeyModifiers::CONTROL) => {
            app.toggle_sidebar();
        }
        (KeyCode::Tab, _) => {
            if let Some(section) = app.sidebar_sections.get_mut(0) {
                section.toggle();
            }
        }
        (KeyCode::Char('p'), KeyModifiers::CONTROL) => {
            app.dialog = Some(Dialog::SessionSwitcher);
        }
        (KeyCode::Esc, _) => {
            app.dialog = None;
        }
        (KeyCode::Enter, _) => {
            if *is_streaming {
                return;
            }
            let text = input.take();
            if text.is_empty() {
                return;
            }
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
            input.insert_char(c);
        }
        (KeyCode::Backspace, _) => {
            input.backspace();
        }
        (KeyCode::Delete, _) => {
            input.delete();
        }
        (KeyCode::Left, _) => {
            input.cursor_left();
        }
        (KeyCode::Right, _) => {
            input.cursor_right();
        }
        (KeyCode::Up, _) => {
            if let Some(s) = history.navigate_prev() {
                input.set_text(s);
            }
        }
        (KeyCode::Down, _) => {
            if let Some(s) = history.navigate_next() {
                input.set_text(s);
            } else {
                input.clear();
            }
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
                if app.switch_theme(name) {
                    app.status_message = format!("Switched to theme: {}", name);
                } else {
                    app.status_message = format!("Unknown theme: {}", name);
                }
            } else {
                app.dialog = Some(Dialog::ThemeSelector);
            }
        }
        "/help" | "/?" => {
            app.dialog = Some(Dialog::Help);
        }
        "/clear" => {
            app.messages.clear();
            app.scroll_to_bottom();
        }
        "/quit" => {
            app.quit();
        }
        _ => {
            app.status_message = format!("Unknown command: {}", cmd);
        }
    }
    input.clear();
    history.push(text.to_string());
}

fn main() -> io::Result<()> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.hide_cursor()?;

    let _guard = Cleanup;

    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();
    if let Err(e) = ctrlc::set_handler(move || {
        r.store(false, Ordering::Relaxed);
    }) {
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

    while running.load(Ordering::Relaxed) && !app.should_quit {
        terminal.draw(|f| {
            let area = f.area();
            let term_width = area.width;
            let sidebar_visible = app.show_sidebar || (app.sidebar_auto && term_width > 120);

            let chunks = if sidebar_visible && term_width > 120 {
                Layout::default().direction(Direction::Horizontal)
                    .constraints([Constraint::Min(0), Constraint::Length(42)])
                    .split(area)
            } else {
                Layout::default().direction(Direction::Horizontal)
                    .constraints([Constraint::Percentage(100), Constraint::Length(0)])
                    .split(area)
            };

            let vertical = Layout::default().direction(Direction::Vertical)
                .constraints([
                    Constraint::Length(1),   // header
                    Constraint::Min(3),      // chat
                    Constraint::Length(4),   // input (2 lines + borders)
                    Constraint::Length(1),   // status bar
                ])
                .split(chunks[0]);

            header::render_header(f, vertical[0], &app.agent_id, app.theme_registry.current_theme());
            chat_panel::render_chat_panel(f, vertical[1], &app.messages, app.scroll_offset, app.theme_registry.current_theme(), true);
            input_bar::render_input_bar(f, vertical[2], &input, app.theme_registry.current_theme(), !is_streaming, &app.agent_id, "gpt-4", app.session_stats.token_count);
            status_bar::render_status_bar(f, vertical[3], &app.agent_id, "default", app.theme_registry.current_theme());

            if sidebar_visible && term_width > 120 {
                sidebar::render_sidebar(
                    f, chunks[1],
                    &mut app.sidebar_sections,
                    &app.tool_stats, &app.session_stats, &app.system_stats,
                    app.theme_registry.current_theme(),
                );
            }

            if app.show_sidebar && term_width <= 120 {
                let overlay = Layout::default().direction(Direction::Horizontal)
                    .constraints([Constraint::Min(0), Constraint::Length(42)])
                    .split(area);

                f.render_widget(Clear, area);

                let backdrop = Block::default()
                    .style(Style::default().bg(Color::Rgb(0, 0, 0)).fg(Color::Rgb(0, 0, 0)));
                f.render_widget(backdrop, area);

                sidebar::render_sidebar(
                    f, overlay[1],
                    &mut app.sidebar_sections,
                    &app.tool_stats, &app.session_stats, &app.system_stats,
                    app.theme_registry.current_theme(),
                );
            }

            if let Some(ref dialog) = app.dialog {
                dialogs::render_dialog(f, area, dialog, &app);
            }
        })?;

        if crossterm_event::poll(Duration::from_millis(100))? {
            if let Event::Key(key) = crossterm_event::read()? {
                if key.kind == KeyEventKind::Press {
                    handle_key(key.code, key.modifiers, &mut app, &mut input, &mut history, &mut agent_client, &tx, &mut is_streaming);
                }
            }
        }

        if is_streaming {
            while let Ok(event) = rx.try_recv() {
                match event {
                    TuiEvent::ToolStart { tool, .. } => {
                        app.track_tool_start(&tool);
                    }
                    TuiEvent::ToolDone { tool, .. } => {
                        app.track_tool_done(&tool);
                    }
                    TuiEvent::ToolError { tool, .. } => {
                        app.track_tool_error(&tool);
                    }
                    TuiEvent::Done(_) | TuiEvent::JsonRpcDone(_) => {
                        app.finalize_last_message();
                        app.session_stats.message_count = app.messages.len();
                        app.session_stats.agent_name = app.agent_id.clone();
                        is_streaming = false;
                    }
                    TuiEvent::JsonRpcError(_) => {
                        app.finalize_last_message();
                        is_streaming = false;
                    }
                    e => {
                        app.append_to_last(e);
                        if app.scroll_offset == usize::MAX {
                            // stays at MAX which means "follow bottom"
                        }
                    }
                }
            }
        }
    }

    agent_client.close();
    drop(_guard);
    terminal.show_cursor()?;
    Ok(())
}
