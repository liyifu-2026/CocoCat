# CocoCat UI → Paperclip Alignment Design

**Date:** 2026-05-04
**Status:** Approved
**Approach:** Full alignment (三栏布局 + 新组件 + 视觉设计系统)

## Overview

Align CocoCat's web-ui (React + Vite + Tailwind v4 + shadcn/ui) with Paperclip's UI architecture, adding a three-column layout, new interactive components, visual design system alignment, and selective Paperclip concepts.

## Layout Architecture

### Three-Column Layout

```
[Rail 44px] [Sidebar 220px] [Main Content + BreadcrumbBar + PropertiesPanel 320px]
```

**Rail** (`CompanyRail.tsx`):
- Fixed 44px wide, vertical left rail
- Brand icon at top
- Navigation section indicators (no company switching needed)
- Bottom: user avatar/logout

**Sidebar** (`Sidebar.tsx`):
- Expanded from pure-icon 56px to text+icon 220px
- Section headers: uppercase 11px muted text
- Nav items: 13px text with lucide icons, active state with background highlight
- Bottom: logout link

**Main Area**:
- Flex column: BreadcrumbBar (top) + scrollable `<main>` content
- Right side: optional PropertiesPanel (320px, animated width)

### Provider Tree

```
main.tsx
├─ QueryClientProvider
│  ├─ ThemeProvider
│  │  ├─ BrowserRouter
│  │  │  ├─ AuthProvider (existing)
│  │  │  │  ├─ SidebarProvider (existing, extended)
│  │  │  │  │  ├─ TooltipProvider (Radix)
│  │  │  │  │  │  ├─ DialogProvider ← NEW
│  │  │  │  │  │  │  ├─ BreadcrumbProvider ← NEW
│  │  │  │  │  │  │  │  ├─ PanelProvider ← NEW
│  │  │  │  │  │  │  │  │  ├─ LiveUpdatesProvider ← NEW
│  │  │  │  │  │  │  │  │  │  ├─ App (Routes)
```

## New Components

### 1. CommandPalette
- **Trigger:** Cmd+K / Ctrl+K
- **Library:** cmdk via shadcn/ui Command component
- **Sections:** Actions (create agent/scene), Pages (nav links), Agents (searchable), Scenes (searchable)
- **Integration:** Fetches agents/scenes via @tanstack/react-query, calls DialogProvider actions

### 2. BreadcrumbBar
- **Provider:** BreadcrumbContext provides `breadcrumbs[]` + `setBreadcrumbs()`
- **Rendering:** Empty → toolbar row with ⌘K button; Single → h1 title; Multiple → breadcrumb trail
- **Style:** h-12, border-bottom, shrink-0
- **Mobile:** sticky with backdrop-blur
- **Auto:** Updates document.title

### 3. PropertiesPanel
- **Provider:** PanelContext provides `panelContent`, `visible`, `openPanel()`, `closePanel()`
- **Width:** 320px with width transition animation (200ms)
- **Persistence:** localStorage for visibility preference
- **Content:** Per-page context-aware (agent detail, chat group info, scene config, etc.)

### 4. DialogProvider
- **Pattern:** Split context (DialogStateContext + DialogActionsContext) to prevent unnecessary re-renders
- **Dialogs:** NewAgentDialog, NewSceneDialog, NewGroupDialog
- **Actions:** `openNewAgent()`, `openNewScene()`, `openNewGroup()` — callable from any component

### 5. LiveUpdatesProvider
- **Connection:** WebSocket to existing `/ws` endpoint
- **Reconnect:** Exponential backoff (1s, 2s, 4s, 8s, 15s max)
- **Events:** `agent.status` → invalidate agents query; `message.new` → toast; heartbeat keepalive
- **Toast gating:** Max 3 toasts per 10s window per category

## Visual Design System

### CSS Variables (index.css additions)
- `--color-chart-1` through `--chart-5` for chart colors
- `--color-sidebar-primary` / `--sidebar-primary-foreground` for sidebar active states
- `color-scheme: light/dark` in root selectors

### Animations
- `dashboard-activity-enter`: fade + scale + slide-up (520ms) with blur
- `dashboard-activity-highlight`: pulse highlight (920ms)
- `cot-line-slide-in/out`: chain-of-thought line transitions (300ms)
- `shimmer-text`: gradient sweep for working states (2.5s)
- Dialog content max-width transition (200ms)
- All animations respect `prefers-reduced-motion`

### Scrollbar Styling
- Dark mode custom scrollbars (8px, dark track/thumb)
- `.scrollbar-auto-hide` utility class (reserves space, shows on hover)

### Mobile
- `touch-action: manipulation` on interactive elements
- `@media (pointer: coarse)` — 44px minimum touch targets
- Sidebar: fixed overlay on mobile with backdrop

## Files to Modify

### New Files
- `src/components/CommandPalette.tsx`
- `src/components/BreadcrumbBar.tsx`
- `src/components/PropertiesPanel.tsx`
- `src/components/CompanyRail.tsx`
- `src/context/DialogContext.tsx`
- `src/context/BreadcrumbContext.tsx`
- `src/context/PanelContext.tsx`
- `src/context/LiveUpdatesContext.tsx`

### Modified Files
- `src/index.css` — Add Paperclip CSS variables, animations, scrollbar, mobile styles
- `src/main.tsx` — Add new Provider wrappers
- `src/App.tsx` — Update routes structure if needed
- `src/components/Layout.tsx` — Refactor to three-column layout
- `src/components/Sidebar.tsx` — Expand to text+icon with navigation structure
- `src/pages/*` — Each page adds `setBreadcrumbs()` call, optional panel content

## Implementation Order

1. CSS variables + animations in index.css
2. New providers (Breadcrumb, Dialog, Panel, LiveUpdates)
3. CompanyRail + Sidebar rewrite
4. Layout.tsx three-column restructure
5. BreadcrumbBar + PropertiesPanel
6. CommandPalette
7. Per-page breadcrumb/panel integration
8. Mobile responsive adaptation

## Design Decisions

- **No company routing:** CocoCat is single-tenant; Paperclip's company-prefix routing is not needed
- **No dnd rail:** CocoCat has one "company" — rail is simplified to navigation sections
- **No plugin system:** CocoCat doesn't have Paperclip's plugin architecture; plugin slots are omitted
- **Keep existing pages:** All CocoCat functionality preserved, only layout/styling changes
- **shadcn/ui alignment:** Both projects use shadcn/ui New York style — ensure radius=0 consistency
