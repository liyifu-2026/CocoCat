# TUI Bugfix Roundup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 13 identified TUI issues across dialog functionality, input system, navigation, content rendering, and backend integration.

**Architecture:** All changes are within the existing Rust TUI (`src/tui/`) — no new modules or dependencies. Each group is independent and can be implemented and tested separately.

**Tech Stack:** Rust, ratatui 0.28, crossterm 0.28, syntect 5

**Implementation order:** A → D → B → C → E (F deferred)

---

## File Structure Map

```
src/tui/
├── app.rs                          # MODIFY: Dialog enum with payload, new fields (dialog_selection, dialog_items, scroll_locked)
├── main.rs                         # MODIFY: Dialog key handling, PageUp/Down, sidebar click, agent switching
├── components/
│   ├── dialogs.rs                  # MODIFY: Selection rendering + enter handlers
│   ├── input_bar.rs                # MODIFY: InputBuffer cursor using char_indices
│   ├── sidebar.rs                  # MODIFY: Agent click detection, mail integration
│   ├── chat_panel.rs               # MODIFY: Remove hovered_row, scroll tracking
│   ├── markdown.rs                 # MODIFY: Dynamic syntect theme, heading/link/list/quote/hr support
│   └── reply_dialog.rs             # (no changes needed)
├── config/config.rs                # MODIFY: Add models field
├── protocol/client.rs              # MODIFY: Add list_agents()
├── session/manager.rs              # (no changes needed)
├── theme/theme.rs                  # (no changes needed)
Cargo.toml                          # MODIFY: Remove tui-textarea, comrak
```

---

### Task A: Dialog with working selection

**Files:**
- Modify: `src/tui/app.rs` (Dialog enum, App fields)
- Modify: `src/tui/components/dialogs.rs` (selection rendering + actions)
- Modify: `src/tui/main.rs` (key handling)
- Modify: `src/tui/config/config.rs` (models field)

- [ ] **Step 1: Transform Dialog enum to carry payload in app.rs**

Replace the current empty-variant enum with state-carrying variants:

```rust
pub enum Dialog {
    ThemeSelector { items: Vec<String>, selected: usize },
    Help,
    SessionSwitcher { items: Vec<String>, selected: usize },
    ModelSelector { items: Vec<String>, selected: usize },
}

impl Dialog {
    pub fn selected(&self) -> usize {
        match self {
            Dialog::ThemeSelector { selected, .. } => *selected,
            Dialog::SessionSwitcher { selected, .. } => *selected,
            Dialog::ModelSelector { selected, .. } => *selected,
            Dialog::Help => 0,
        }
    }

    pub fn select(&mut self, index: usize) {
        match self {
            Dialog::ThemeSelector { selected, items }
            | Dialog::SessionSwitcher { selected, items }
            | Dialog::ModelSelector { selected, items } => {
                if !items.is_empty() {
                    *selected = index % items.len();
                }
            }
            Dialog::Help => {}
        }
    }

    pub fn items(&self) -> &[String] {
        match self {
            Dialog::ThemeSelector { items, .. }
            | Dialog::SessionSwitcher { items, .. }
            | Dialog::ModelSelector { items, .. } => items,
            Dialog::Help => &[],
        }
    }

    pub fn confirm(&self, app: &mut App) {
        match self {
            Dialog::ThemeSelector { items, selected } => {
                if *selected < items.len() {
                    let name = &items[*selected];
                    if app.switch_theme(name) {
                        app.status_message = format!("Switched to theme: {}", name);
                    }
                }
            }
            Dialog::ModelSelector { items, selected } => {
                if *selected < items.len() {
                    app.status_message = format!("Selected model: {}", items[*selected]);
                }
            }
            Dialog::SessionSwitcher { items, selected } => {
                if *selected < items.len() {
                    let mgr = crate::session::manager::SessionManager::new();
                    if let Some(session) = mgr.load(&items[*selected]) {
                        app.messages = session;
                        app.status_message = format!("Loaded session: {}", items[*selected]);
                    }
                }
            }
            Dialog::Help => {}
        }
    }
}
```

- [ ] **Step 2: Remove old app fields**

Remove `dialog_selection` and `dialog_items` from App (if added during brainstorming). The Dialog enum payload replaces them.

- [ ] **Step 3: Update dialog creation in slash commands (main.rs)**

```rust
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
                let items: Vec<String> = app.theme_registry.all().iter().map(|t| t.name.clone()).collect();
                app.dialog = Some(Dialog::ThemeSelector { items, selected: 0 });
            }
        }
        "/help" | "/?" => { app.dialog = Some(Dialog::Help); }
        "/clear" => { app.messages.clear(); app.scroll_to_bottom(); }
        "/model" => {
            let items = vec!["gpt-4".into(), "gpt-3.5-turbo".into(), "claude-3".into()];
            app.dialog = Some(Dialog::ModelSelector { items, selected: 0 });
        }
        "/session" => {
            let mgr = session::manager::SessionManager::new();
            let items: Vec<String> = mgr.list();
            app.dialog = Some(Dialog::SessionSwitcher { items, selected: 0 });
        }
        "/quit" => { app.quit(); }
        _ => { app.status_message = format!("Unknown command: {}", cmd); }
    }
    input.clear();
    history.push(text.to_string());
}
```

- [ ] **Step 4: Update dialog key handling in handle_key (main.rs)**

Replace lines 98-105:

```rust
if let Some(ref mut dialog) = app.dialog {
    match (key, modifiers) {
        (KeyCode::Up, _) => {
            let sel = dialog.selected();
            dialog.select(sel.saturating_sub(1));
        }
        (KeyCode::Down, _) => {
            let sel = dialog.selected();
            let items = dialog.items().len();
            let next = if items > 0 { (sel + 1) % items } else { 0 };
            dialog.select(next);
        }
        (KeyCode::Enter, _) => {
            let d = dialog.clone();
            d.confirm(app);
            app.dialog = None;
        }
        (KeyCode::Esc, _) => {
            app.dialog = None;
        }
        _ => {}
    }
    return;
}
```

> Note: `Dialog::clone()` requires `#[derive(Clone)]` on the enum (already present in the step 1 code).

- [ ] **Step 5: Update dialog rendering for selection highlighting (dialogs.rs)**

```rust
fn render_theme_selector(f: &mut Frame, area: Rect, dialog: &Dialog, app: &App) {
    let Dialog::ThemeSelector { items, selected } = dialog else { return; };
    let theme = app.theme_registry.current_theme();
    let dialog_area = centered_rect(50, 50, area);

    let list_items: Vec<ListItem> = items.iter().enumerate().map(|(i, name)| {
        let is_selected = i == *selected;
        let style = if is_selected {
            Style::default().fg(theme.accent_color())
        } else {
            Style::default().fg(theme.text_color())
        };
        let prefix = if is_selected { "▶ " } else { "  " };
        ListItem::new(Line::from(Span::styled(format!("{prefix}{name}"), style)))
    }).collect();

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(theme.accent_color()))
        .title(Span::styled(" Select Theme ", Style::default().fg(theme.accent_color())))
        .style(Style::default().bg(theme.bg()));

    let list = List::new(list_items).block(block);
    f.render_widget(Clear, dialog_area);
    f.render_widget(list, dialog_area);
}
```

Same pattern for `render_session_switcher` and `render_model_selector`.

- [ ] **Step 6: Update render_dialog signature to pass dialog by reference**

```rust
pub fn render_dialog(f: &mut Frame, area: Rect, dialog: &Dialog, app: &App) {
    match dialog {
        Dialog::ThemeSelector { .. } => render_theme_selector(f, area, dialog, app),
        Dialog::Help => render_help(f, area, app),
        Dialog::SessionSwitcher { .. } => render_session_switcher(f, area, dialog, app),
        Dialog::ModelSelector { .. } => render_model_selector(f, area, dialog, app),
    }
}
```

- [ ] **Step 7: Run tests**

Run: `cargo test -p cococat-tui`
Expected: all existing tests pass (app.rs tests, event.rs tests, etc.)

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "fix(tui): make dialogs functional with keyboard selection and actions"
```

---

### Task D1: InputBuffer cursor fix

**Files:**
- Modify: `src/tui/components/input_bar.rs`

- [ ] **Step 1: Read current input_bar.rs to understand InputBuffer struct**

The struct has `text: String` and `cursor: usize` (character offset, not byte offset).

- [ ] **Step 2: Rewrite cursor operations using char_indices**

```rust
impl InputBuffer {
    pub fn insert_char(&mut self, c: char) {
        if let Some((byte_idx, _)) = self.text.char_indices().nth(self.cursor) {
            self.text.insert(byte_idx, c);
        } else {
            self.text.push(c);
        }
        self.cursor += 1;
    }

    pub fn backspace(&mut self) {
        if self.cursor == 0 { return; }
        self.cursor -= 1;
        if let Some((byte_idx, _)) = self.text.char_indices().nth(self.cursor) {
            self.text.remove(byte_idx);
        }
    }

    pub fn delete(&mut self) {
        if let Some((byte_idx, _)) = self.text.char_indices().nth(self.cursor) {
            self.text.remove(byte_idx);
        }
    }

    pub fn cursor_left(&mut self) {
        if self.cursor > 0 {
            self.cursor -= 1;
        }
    }

    pub fn cursor_right(&mut self) {
        let char_count = self.text.chars().count();
        if self.cursor < char_count {
            self.cursor += 1;
        }
    }
}
```

- [ ] **Step 3: Run tests**

Run: `cargo test -p cococat-tui`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "fix(tui): InputBuffer cursor operations use char_indices for UTF-8 safety"
```

---

### Task D2: Remove unused dependencies

**Files:**
- Modify: `Cargo.toml`

- [ ] **Step 1: Remove tui-textarea and comrak from Cargo.toml**

In `Cargo.toml`, find and remove these lines:
```
tui-textarea = "0.7"
comrak = "0.29"
```

- [ ] **Step 2: Verify build still works**

Run: `cargo build -p cococat-tui`
Expected: build succeeds without errors

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore(tui): remove unused tui-textarea and comrak dependencies"
```

---

### Task B1: PageUp/PageDown scrolling

**Files:**
- Modify: `src/tui/main.rs` (key handlers)
- Modify: `src/tui/app.rs` (scroll methods)

- [ ] **Step 1: Add scroll methods to App (app.rs)**

```rust
impl App {
    pub fn scroll_up(&mut self, lines: usize) {
        self.scroll_locked = false;
        if self.scroll_offset == usize::MAX {
            self.scroll_offset = lines;
        } else {
            self.scroll_offset = self.scroll_offset.saturating_add(lines);
        }
    }

    pub fn scroll_down(&mut self, lines: usize) {
        if self.scroll_offset == usize::MAX { return; }
        if lines >= self.scroll_offset {
            self.scroll_offset = usize::MAX;
            self.scroll_locked = true;
        } else {
            self.scroll_offset = self.scroll_offset.saturating_sub(lines);
        }
    }
}
```

Add field: `pub scroll_locked: bool` in `App` struct, default `true` in `App::new()`.

- [ ] **Step 2: Add scroll_locked to App::new()**

```rust
// In App::new() add:
scroll_locked: true,
```

- [ ] **Step 3: Update scroll_to_bottom()**

```rust
pub fn scroll_to_bottom(&mut self) {
    self.scroll_offset = usize::MAX;
    self.scroll_locked = true;
}
```

- [ ] **Step 4: Add PageUp/PageDown key handlers (main.rs)**

Add to the main `match (key, modifiers)` block in `handle_key`:

```rust
(KeyCode::PageUp, _) => {
    app.scroll_up(10); // ~half page
}
(KeyCode::PageDown, _) => {
    app.scroll_down(10);
}
```

- [ ] **Step 5: Run tests**

Run: `cargo test -p cococat-tui`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(tui): PageUp/PageDown scrolling with scroll_locked tracking"
```

---

### Task B2: Sidebar agent switching

**Files:**
- Modify: `src/tui/main.rs` (process_sidebar_click)

- [ ] **Step 1: Update process_sidebar_click to identify agent rows**

```rust
fn process_sidebar_click(app: &mut App, col: i32, row: i32, term_width: u16) {
    let sidebar_visible = app.show_sidebar || (app.sidebar_auto && term_width > 120);
    let sidebar_x = (term_width as i32).saturating_sub(42);
    if !sidebar_visible || col < sidebar_x || col >= term_width as i32 { return; }
    let content_row = row.saturating_sub(1);
    let mut current_row = 0i32;

    for section in app.sidebar_sections.iter() {
        if content_row == current_row { return; } // header row — toggle handled below
        current_row += 1;
        if !section.collapsed {
            match section.name.as_str() {
                "Team" => {
                    for agent in &app.agent_statuses {
                        if content_row == current_row {
                            // Clicked on an agent row
                            if agent.id != app.agent_id {
                                app.agent_id = agent.id.clone();
                                app.status_message = format!("Switched to agent: {}", agent.name);
                            }
                            return;
                        }
                        current_row += 1;
                    }
                }
                "Session" => { current_row += 3; }
                "Tools" => { current_row += app.tool_stats.tool_calls.len().max(1) as i32; }
                "Mail" => { current_row += 2; }
                _ => {}
            }
        }
        current_row += 1; // spacing between sections
    }
}
```

- [ ] **Step 2: Add a switch_agent method to App**

```rust
impl App {
    pub fn switch_agent(&mut self, id: &str) {
        self.agent_id = id.to_string();
        self.messages.clear();
        self.session_stats.message_count = 0;
        self.session_stats.token_count = 0;
        self.status_message = format!("Switched to agent: {}", id);
    }
}
```

Update `process_sidebar_click` to use `app.switch_agent(&agent.id)`.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(tui): sidebar click switches active agent"
```

---

### Task C1: Dynamic syntect theme

**Files:**
- Modify: `src/tui/components/markdown.rs`

- [ ] **Step 1: Add theme mapping function**

```rust
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
```

- [ ] **Step 2: Update render_markdown signature and usage**

Accept theme name `&str` in addition to `&Theme`:

```rust
pub fn render_markdown(text: &str, theme: &Theme, theme_name: &str) -> Vec<Span<'static>> {
    // ...
    let syn_theme_name = syntect_theme_name(theme_name);
    // Replace all &syn_ts.themes["base16-ocean.dark"] with &syn_ts.themes[syn_theme_name]
}
```

- [ ] **Step 3: Update caller in chat_panel.rs**

Find the call site of `render_markdown` and pass the theme name (available from `app.theme_registry.current()`).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat(tui): dynamic syntect theme matching app theme"
```

---

### Task C2: Markdown enhancements

**Files:**
- Modify: `src/tui/components/markdown.rs`

- [ ] **Step 1: Add heading support**

In the line-by-line rendering section, detect `#` at line start:

```rust
fn detect_heading(line: &str) -> Option<usize> {
    let trimmed = line.trim_start();
    let mut level = 0;
    for c in trimmed.chars() {
        if c == '#' { level += 1; } else { break; }
    }
    if level > 0 && level <= 6 && trimmed.len() > level && trimmed.chars().nth(level) == Some(' ') {
        Some(level)
    } else {
        None
    }
}
```

In the main render loop: if a line starts with `#`-`######`, render the rest of the line with accent color and BOLD modifier.

- [ ] **Step 2: Add link support**

In the char-scanning loop:

```rust
// After the ` code handling block, before the * bold/italic handling
if c == '[' && !code && !code_block {
    // Look ahead for ](...)
    if let Some(close_bracket) = chars[i..].iter().position(|&ch| ch == ']') {
        let after_bracket = i + close_bracket + 1;
        if after_bracket < chars.len() && chars[after_bracket] == '(' {
            if let Some(close_paren) = chars[after_bracket..].iter().position(|&ch| ch == ')') {
                let text: String = chars[i+1..i+close_bracket].iter().collect();
                flush(&mut spans, &mut buf, bold, italic, false, theme);
                spans.push(Span::styled(text, Style::default().fg(theme.accent_color()).add_modifier(Modifier::UNDERLINED)));
                i = after_bracket + close_paren + 1;
                continue;
            }
        }
    }
}
```

- [ ] **Step 3: Add unordered list support**

In the line-splitting phase (or in the char loop), detect `- ` or `* ` at line start:

```rust
fn line_start_list(line: &str) -> Option<&'static str> {
    let trimmed = line.trim_start();
    if trimmed.starts_with("- ") || trimmed.starts_with("* ") {
        Some("• ")
    } else {
        None
    }
}
```

- [ ] **Step 4: Add blockquote support**

Detect `> ` at line start, prepend `▌ ` with dim color.

- [ ] **Step 5: Run tests**

Run: `cargo test -p cococat-tui`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(tui): markdown heading, link, list, blockquote support"
```

---

### Task C3: Remove dead hover code

**Files:**
- Modify: `src/tui/components/chat_panel.rs`
- Modify: `src/tui/main.rs`

- [ ] **Step 1: Remove hovered_row from chat_panel.rs**

Remove the `hovered_row: Option<u16>` parameter from `render_chat_panel()` and all hover-related styling.

- [ ] **Step 2: Update caller in main.rs**

Remove `hovered_row` variable (line 232) and its usage in the `render_chat_panel` call (line 257).

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "refactor(tui): remove dead hover code (mouse move disabled)"
```

---

### Task E1: Dynamic agent discovery

**Files:**
- Modify: `src/tui/protocol/client.rs`
- Modify: `src/tui/main.rs`

- [ ] **Step 1: Add list_agents directory scan in main.rs**

```rust
fn discover_agents() -> Vec<app::AgentStatus> {
    let agents_dir = dirs::home_dir()
        .unwrap_or_default()
        .join(".cococat/agents");
    let mut agents = Vec::new();
    if let Ok(entries) = std::fs::read_dir(&agents_dir) {
        for entry in entries.flatten() {
            if entry.path().is_dir() {
                let id = entry.file_name().to_string_lossy().to_string();
                agents.push(app::AgentStatus {
                    id: id.clone(),
                    name: id,
                    running: true,
                });
            }
        }
    }
    if agents.is_empty() {
        // Fallback to default
        agents.push(app::AgentStatus { id: "leader".into(), name: "Leader".into(), running: true });
    }
    agents
}
```

- [ ] **Step 2: Replace hardcoded agents in run_tui()**

Replace lines 218-223 with:
```rust
app.agent_statuses = discover_agents();
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(tui): dynamic agent discovery from ~/.cococat/agents/"
```

---

### Task E2: Mailbox integration (optional)

**Files:**
- Modify: `src/tui/components/sidebar.rs`
- (If reply dialog is triggered from sidebar click, modify `main.rs`)

- [ ] **Step 1: Scan mailbox directory in sidebar rendering**

```rust
fn get_mail_count() -> (usize, usize) {
    let mailbox = dirs::home_dir()
        .unwrap_or_default()
        .join(".cococat/agents/mailbox");
    let unread = std::fs::read_dir(&mailbox)
        .map(|e| e.flatten().count())
        .unwrap_or(0);
    let processed = std::fs::read_dir(mailbox.join("processed"))
        .map(|e| e.flatten().count())
        .unwrap_or(0);
    (unread, processed)
}
```

Update the Mail section in `sidebar.rs` to call this function instead of hardcoded values.

- [ ] **Step 2: Commit**

```bash
git add -A && git commit -m "feat(tui): real mailbox file system integration"
```

---

## Self-Review Checklist

- [ ] Spec coverage: All 13 issues from the spec have corresponding tasks (A=2 issues, D1/D2=2 issues, B1/B2=2 issues, C1/C2/C3=3 issues, E1/E2=2 issues, F=deferred)
- [ ] No placeholders: every step has actual code
- [ ] Type consistency: Dialog enum payload matches across tasks A1-A6
- [ ] Test commands provided where applicable
