use std::io;
use ratatui::{
    backend::CrosstermBackend,
    Terminal,
};
use crossterm::{
    event::{self, Event, KeyCode},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};

mod config;
mod theme;

struct Cleanup;

impl Drop for Cleanup {
    fn drop(&mut self) {
        let _ = disable_raw_mode();
        let _ = execute!(io::stdout(), LeaveAlternateScreen);
    }
}

fn main() -> io::Result<()> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.hide_cursor()?;

    let _guard = Cleanup;

    let running = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(true));
    let r = running.clone();
    if let Err(e) = ctrlc::set_handler(move || {
        r.store(false, std::sync::atomic::Ordering::Relaxed);
    }) {
        eprintln!("Warning: could not set Ctrl+C handler: {e}");
    }

    while running.load(std::sync::atomic::Ordering::Relaxed) {
        terminal.draw(|f| {
            let area = f.area();
            let text = ratatui::text::Text::raw("CocoCat TUI — press 'q' to quit");
            f.render_widget(text, area);
        })?;

        if event::poll(std::time::Duration::from_millis(100))? {
            if let Event::Key(key) = event::read()? {
                if key.code == KeyCode::Char('q') {
                    break;
                }
            }
        }
    }

    drop(_guard);
    terminal.show_cursor()?;
    Ok(())
}
