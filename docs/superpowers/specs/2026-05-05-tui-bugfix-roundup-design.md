# TUI Bugfix Roundup

## Overview

Fix all remaining TUI issues identified after the initial UX redesign. 13 issues grouped into 6 workstreams, implemented in order: A → D → B → C → E → F.

---

## Group A: Dialog Functionality

**Files affected:** `src/tui/app.rs`, `src/tui/components/dialogs.rs`, `src/tui/main.rs`, `src/tui/config/config.rs`

### Current state
Three dialogs (ThemeSelector, ModelSelector, SessionSwitcher) render lists but cannot actually select anything. Up/Down does nothing, Enter just closes without action.

### Design

**App struct additions:**
- `dialog_selection: usize` — selected item index in current dialog
- `dialog_items: Vec<String>` — item list for current dialog

**Alternative (cleaner):** Make `Dialog` carry state:
```rust
pub enum Dialog {
    ThemeSelector { items: Vec<String>, selected: usize },
    Help,
    SessionSwitcher { items: Vec<String>, selected: usize },
    ModelSelector { items: Vec<String>, selected: usize },
}
```

Use the enum payload approach — it's self-contained and avoids cross-field invariants.

**Key handling** (`main.rs` lines 98-105):
- `Up` → `selected = selected.saturating_sub(1)` (wrap to last if at 0)
- `Down` → `selected = (selected + 1) % items.len()`
- `Enter` → execute the action for the selected item:
  - ThemeSelector: `app.theme_registry.switch(name)` + status message
  - ModelSelector: `app.switch_model(name)` + status message  
  - SessionSwitcher: `app.load_session(name)` + status message
- `Esc` → close dialog, no action

**Model list source:** Read from `Config.chat.models` if available, fallback to `["gpt-4", "gpt-3.5-turbo", "claude-3"]`.

**Session list source:** Already reads from `SessionManager::list()`.

**Rendering changes** (`dialogs.rs`):
- Selected item gets accent color + `▶ ` prefix
- Non-selected items get text color + `  ` prefix

---

## Group D: Input System

**Files affected:** `src/tui/components/input_bar.rs`, `Cargo.toml`

### D1: InputBuffer cursor drift

**Root cause:** `insert_char` at line 33-41 checks char boundary but falls back to `push()` (append at end) when cursor points to non-boundary position, causing cursor/text mismatch.

**Fix:** Rewrite cursor tracking to use `char_indices()` consistently. All cursor operations (insert, delete, backspace, left, right) operate on character indices derived from `char_indices()`, never on raw byte offsets.

```rust
fn insert_char(&mut self, c: char) {
    if let Some((byte_idx, _)) = self.text.char_indices().nth(self.cursor) {
        self.text.insert(byte_idx, c);
    } else {
        self.text.push(c);
    }
    self.cursor += 1;
}
```

Same pattern applied to `backspace()`, `delete()`, `cursor_left()`, `cursor_right()`.

### D2: Remove unused dependencies

Remove from `Cargo.toml`:
- `tui-textarea` (unused — using custom InputBuffer)
- `comrak` (unused — using hand-rolled Markdown parser)

---

## Group B: Navigation

**Files affected:** `src/tui/main.rs`, `src/tui/app.rs`, `src/tui/components/sidebar.rs`

### B1: PageUp/PageDown scrolling

Add key handlers in `handle_key`:
```rust
(KeyCode::PageUp, _) => app.scroll_up(page_lines),
(KeyCode::PageDown, _) => app.scroll_down(page_lines),
```

Where `page_lines` is approximately half the visible chat area height (calculated during rendering or passed as a parameter).

### B2: scroll_offset cleanup

**Current:** `scroll_offset = usize::MAX` hack for "scroll to bottom".

**Fix:** Add `App::scroll_locked: bool`:
- `true` (default) = auto-follow latest messages
- User scrolls up → `scroll_locked = false`
- New message arrives and already at bottom → stays at bottom
- User presses PageDown past bottom → re-lock

Remove `usize::MAX` from `scroll_to_bottom()`.

### B3: Sidebar click switches agent

**Current:** `process_sidebar_click()` only toggles section collapse.

**Fix:** When click lands on a row within the Team section, identify which agent name was clicked. Call `app.switch_agent(agent_id)` which:
1. Closes current agent connection
2. Resets messages
3. Opens new agent session

---

## Group C: Content Rendering

**Files affected:** `src/tui/components/markdown.rs`, `src/tui/components/chat_panel.rs`, `src/tui/main.rs`

### C1: Dynamic syntect theme

**Current:** `markdown.rs:41,104` hardcodes `"base16-ocean.dark"`.

**Fix:** Map app theme name to syntect theme name:

| App Theme | Syntect Theme |
|-----------|---------------|
| catppuccin-mocha | `base16-mocha.dark` |
| nord | `base16-nord` |
| dracula | `base16-dracula` |
| tokyonight | `base16-tokyo-night` |
| gruvbox | `base16-gruvbox.dark` |

Fallback to `"base16-ocean.dark"` for unmapped themes.

### C2: Markdown feature additions

Incremental additions to the hand-rolled parser:

| Priority | Feature | Implementation |
|----------|---------|---------------|
| P0 | Headings `#`-`######` | Line-start `#` detection → accent color + bold |
| P1 | Links `[text](url)` | Parse `[...](...)` pattern → accent color + underline modifier |
| P2 | Unordered lists `- ` | Line-start `- ` → prepend `• ` bullet |
| P3 | Ordered lists `1. ` | Line-start digit + `.` → prepend incrementing number |
| P4 | Blockquotes `> ` | Line-start `> ` → prepend `▌ ` vertical bar |
| P5 | Horizontal rules `---` | Line of 3+ dashes → render `─` separator line |

All features use the existing single-pass character-scanning architecture — no new dependencies.

### C3: Remove dead hover code

Remove `hovered_row` parameter from `render_chat_panel` calls and the associated hover logic in `chat_panel.rs`. Mouse move tracking is disabled and not planned for re-enable.

---

## Group E: Backend Integration

**Files affected:** `src/tui/main.rs`, `src/tui/components/sidebar.rs`, `src/tui/protocol/client.rs`

### E1: Dynamic agent discovery

**Current:** 4 agents hardcoded in `main.rs:218-223`.

**Fix:** Add `AgentClient::list_agents()` RPC or scan `~/.cococat/agents/` directory. Populate `app.agent_statuses` dynamically.

### E2: Mailbox integration

**Current:** Mail section shows dummy data.

**Fix:** Scan `~/.cococat/agents/mailbox/` for `.json` dispatch files. Each file = one pending dispatch. Click to open `ReplyDialog`. On send, move file to `processed/` subdirectory.

---

## Group F: Indexed Color

**Files affected:** None (deferred)

**Decision:** No changes. 95%+ of modern terminals support `Color::Rgb` (24-bit). Defer until a concrete need arises (e.g., running on a 256-color terminal).

---

## Implementation Order

A → D → B → C → E → F

Each group is independent. Within Group A, all dialog changes can be done in a single pass.

## Testing

- Unit tests for `InputBuffer` cursor operations (multibyte characters, edge cases)
- Unit tests for `Dialog` selection/wrapping logic
- Unit tests for Markdown parser additions
- Manual verification: each dialog can actually select and execute
- Manual verification: PageUp/PageDown scrolls correctly
- Manual verification: sidebar agent click switches agent
