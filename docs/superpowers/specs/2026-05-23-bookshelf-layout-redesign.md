# Bookshelf & Layout Redesign

**Date**: 2026-05-23
**Status**: Draft

---

## Overview

Redesign CocoCat's 3-panel layout to introduce a dynamic overlay/collapse relationship between the chat area and the operation area, a redesigned infinite-scroll bookshelf, integrated KB browsing, and a Raw upload staging zone.

Key shifts:
- Chat panel overlays the operation area by default; collapses to a narrow rail when operations are active.
- Knowledge base browsing merges with the Bookshelf into one unified page.
- Routing replaces programmatic navigation (`useState`) with react-router.

---

## 1. Chat & Operation Area Layout

### 1.1 Two States

| State | Chat Width | Op Display |
|---|---|---|
| **overlay** | ~420px, `position: absolute`, overlays operation area | Full-width behind chat, content visible but blurred/dimmed |
| **collapsed** | ~72px narrow rail | Full remaining width (`calc(100vw - 76px - 72px)`) |

Chat panel is a **persistent component**: it never unmounts on route changes, preserving session state. It only changes layout mode.

### 1.2 Transition Animation (~300ms)

- `overlay → collapsed`: Chat panel slides `right: 0 → -340px`. Op display gains `margin-right: 72px`. Message area fades out. Narrow rail fades in (avatar + mode icon + expand arrow).
- `collapsed → overlay`: Inverse animation.

### 1.3 Triggers

| Trigger | Behavior |
|---|---|
| Navigate to `/app/knowledge`, `/app/scenes`, `/app/settings`, `/app/memory` | Route change → overlay → collapsed |
| Navigate to `/app/chat` | Route change → collapsed → overlay |
| Click file card in chat (agent attachment) | overlay → collapsed (no route change); op display renders file preview |
| kb-admin agent opens KB document | Same as file card click |
| Click expand arrow on collapsed rail | collapsed → overlay (user manual) |

After collapsing, chat stays collapsed. It does NOT auto-expand when agent finishes. User must manually pull back.

### 1.4 Collapsed Rail (72px)

- Avatar or mode icon (🐱/📚), colored per mode (blue/amber)
- Expand arrow (→) to restore overlay
- Unread message red dot (pulses on new message)
- Breathing edge glow when agent is streaming output
- On hover: slides out 60px showing latest message preview (similar to Discord collapsed member list). Click expands.

### 1.5 Keyboard Shortcuts (New)

| Shortcut | Action |
|---|---|
| `Ctrl+[` | Collapse chat |
| `Ctrl+]` | Expand chat |
| `Ctrl+L` | Focus KB search panel or directory tree search |
| `Escape` | Close file preview / search panel / mode dropdown |

---

## 2. Routing

### 2.1 Route Structure

Replace current `useState("chat")`-based programmatic navigation with react-router:

```
/app/chat                          → Overlay chat (default landing)
/app/chat/:sessionId               → Specific session, overlay chat

/app/knowledge                     → Bookshelf page (chat auto-collapsed), no KB selected
/app/knowledge/:kbName             → Bookshelf, 🔻 on specified KB
/app/knowledge/:kbName/:pageType/:pageName  → Bookshelf, wiki page opened in doc renderer

/app/scenes                        → Scenes page (chat stays collapsed)
/app/settings                      → Settings page
/app/settings/:tab                 → Settings with preselected tab
/app/memory                        → Memory page
```

`Layout` reads route, not `activeNav` state. `LeftNav` buttons become `<Link>` components.

### 2.2 Chat Panel Persistence

ChatPanel is mounted at Layout level, outside `<Outlet />`. It subscribes to route changes to determine overlay vs collapsed, but never unmounts.

---

## 3. Bookshelf Page (`/app/knowledge`)

### 3.1 Vertical Layout

```
┌─────────────────────────────────────────┐
│  Doc Renderer (directory tree + MD)      │
├─────────────────────────────────────────┤
│  ─── 🔻 Bookshelf (single row) ───      │
├─────────────────────────────────────────┤
│  Raw Zone (upload staging)              │
└─────────────────────────────────────────┘
```

### 3.2 Bookshelf Mechanics

- **Single horizontal row**, infinite scroll loop.
- CSS `scroll-snap-type: x mandatory` — each book snaps to center.
- **🔻 indicator**: `position: fixed` centered above shelf. Does not scroll. Reads current `scrollLeft` to determine `selectedIndex`.
- **Infinite loop**: first/last 1-2 books cloned to ends. On reaching clone boundary, silent instant jump to matching real position.
- **Book card**: ~72px wide, ~96px tall. Colorful cover art with SVG pattern + KB name (reuse existing Bookshelf component visuals). Selected book gets glow + slight scale-up.
- **Virtual rendering**: Only render visible ±3 books. Use `@tanstack/react-virtual` or manual offset-based clipping.

### 3.3 🔻 Click → Quick Select Panel

Click the 🔻 arrow: opens a floating command-palette-style search panel.

- Type to filter KBs by name/description.
- Select → shelf `scrollTo` animates to that book.
- Enter or click → panel closes, directory tree refreshes for selected KB.

### 3.4 Doc Renderer (Above Shelf)

**Layout**: Left directory tree (~220px) + Right MD body (remaining width).

**Directory tree**:
- Populated from `GET /api/knowledge/{kbName}/wiki` (entities, concepts, pages).
- Each item clickable → routes to `/app/knowledge/{kbName}/{pageType}/{pageName}`.
- Active item highlighted.
- Top search box filters directory items (reuse backend `GET /api/knowledge/{kbName}/search`).

**MD body**:
- Route drives content: fetches `GET /api/knowledge/{kbName}/wiki/{pageType}/{pageName}`.
- Rendered with `react-markdown` + `remark-gfm` (existing).
- Mermaid diagrams (existing `MermaidBlock`).
- Code blocks with syntax highlighting + copy button.
- Backlinks at bottom (existing API + i18n key).

### 3.5 Raw Zone (Below Shelf)

**Purpose**: Drag-and-drop upload staging area before categorization into a KB.

**Features**:
- Expandable/collapsible section.
- Drag files from OS file manager. Multi-file support.
- File cards show: icon/thumbnail, filename, format badge, size. Each can be deleted.
- Upload progress: pending → parsing → ready.
- "Ask agent to organize" button → chat overlay pops with pre-filled prompt. Agent classifies and indexes files into target KB(s).
- Drag file card onto shelf KB to directly assign without chat (shortcut).
- Backend: files stored under `knowledge/.raw/`. New API endpoints for raw list and delete.

---

## 4. Mode Switching (Namecard Animation)

### 4.1 Animation (~400ms)

- **Gradient**: Two layered divs cross-fade opacity (CSS `transition` on `background` is insufficient for gradients). Blue (default) ↔ amber (kb-admin).
- **Icon**: 🐱 ↔ 📚 with `rotateY(180°)` flip or scale bounce (~300ms `ease-out`).
- **Title**: Old text slides up and fades out; new text slides down and fades in (~250ms staggered).

### 4.2 No Explicit Mode Label

Only the Namecard color + icon indicate mode. Tooltip on hover shows mode name for discoverability. The collapsed chat rail also shows the mode icon in the corresponding color.

### 4.3 Triggers

- `/mode kb-admin` in chat input (existing)
- Mode dropdown on Namecard (existing)
- `Ctrl+K` command palette (existing)

---

## 5. File Click from Chat

### 5.1 File Card in Chat

Agent-attached files render as file cards distinct from message bubbles (bordered, rounded, hover highlight).

### 5.2 Behavior by File Type

| File Type | On Click |
|---|---|
| Wiki page in a KB | Navigate to `/app/knowledge/{kbName}/{pageType}/{pageName}`, directory tree syncs |
| Agent-generated file (report, analysis) | Chat collapses → file preview overlay in op display (no route change, top bar with "← Back to chat") |
| Image (png/jpg/gif/svg) | Open in image viewer |
| PDF | `<iframe>` inline preview |
| Code file (.py/.ts/.js etc.) | Syntax-highlighted code block |
| External link | Open in new tab (browser default, no layout change) |

### 5.3 File Preview Overlay

- Top bar: "← Back to chat" button + filename + source session ID.
- Content area uses appropriate renderer.
- "← Back" restores chat overlay (if no other route change occurred).

---

## 6. Component Architecture

```
Layout
├── LeftNav                  → <Link> to routes (no more activeNav state)
├── ChatPanel (persistent)   → overlay or collapsed based on route context
│   ├── ChatMessages
│   ├── ChatInput
│   └── (collapsed rail render)
├── <Outlet />               → route-driven operation area
│   ├── ChatPage (/app/chat, /app/chat/:sessionId)
│   │   └── DefaultFunc (behind chat overlay, dimmed)
│   ├── BookshelfPage (/app/knowledge/*)
│   │   ├── DocRenderer (directory tree + MD body)
│   │   ├── Bookshelf (infinite scroll + 🔻 + search panel)
│   │   └── RawZone (upload staging)
│   ├── ScenesPage (/app/scenes)
│   ├── SettingsPage (/app/settings, /app/settings/:tab)
│   └── MemoryPage (/app/memory)
└── FilePreviewOverlay       → conditionally rendered overlay for non-KB files
```

Key removals:
- `OpDisplay` — replaced by `<Outlet />` + route components.
- `KbAdminFunc` — absorbed into BookshelfPage.
- `Layout.activeNav` state — replaced by route.
- `KnowledgeView` — merged into BookshelfPage (raw upload replaces the separate create/upload view, KB list is the bookshelf itself).

---

## 7. Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| ≥1280px (desktop) | Full 3-panel layout with all features |
| 768-1280px (tablet) | LeftNav icon-only (existing). Chat ~320px wide. Bookshelf row shorter. |
| <768px (mobile) | Keep existing `MobileBottomNav`. Op display and chat become two full-screen tabbed pages. Overlay/collapsed mechanic not applicable. Bookshelf becomes compact horizontal slider. |

---

## 8. API Changes

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/knowledge/{kbName}/wiki` | Existing | Directory tree data |
| `GET /api/knowledge/{kbName}/wiki/{pageType}/{pageName}` | Existing | MD page content |
| `GET /api/knowledge/{kbName}/search` | Existing | Directory tree search |
| `GET /api/knowledge/.raw` | New | List raw staging files |
| `DELETE /api/knowledge/.raw/{filename}` | New | Delete raw staging file |
| `POST /api/knowledge` | Existing | Create KB (used by agent during organize) |
| `POST /api/knowledge/{kbName}/upload` | Existing | Upload to KB (used by agent during organize) |

---

## 9. Dependencies

No new external dependencies required. All UI primitives exist (shadcn/ui, Tailwind CSS, `react-router-dom`, `@tanstack/react-query`, `@tanstack/react-virtual` is already in the project for potential virtual scrolling).

---

## 10. Migration Notes

- Convert `Layout` from `useState("chat")` to `useLocation()` → derive active nav from path.
- Convert `LeftNav` buttons from `onClick` callbacks to `<Link to="...">`.
- Extract `OpDisplay` sub-views into independent route components.
- `ChatPanel` moves from inside `<Outlet />` to Layout level for persistence.
- `Namecard` and `VizEngine` — Namecard becomes part of ChatPage/BookshelfPage headers (not shared), VizEngine stays as a floating overlay.
- Mode context (`ModeContext`) and session store (`useSessionStore`) remain unchanged.
