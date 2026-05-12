# Sidebar Nav Items: Drag-to-Reorder & Hide

## Problem

The sidebar has 12 static navigation items in a fixed order. Users cannot customize which items appear or in what order.

## Solution

Extend the sidebar with:
1. **Edit mode** — toggle in/out via a pencil button at sidebar bottom
2. **Drag-to-reorder** — using `@dnd-kit` library, items are sortable in edit mode
3. **Per-item hide/show** — each item gets a toggle button in edit mode; hidden items are not rendered in normal mode

## State

`SidebarContext` is extended with:
- `navOrder: string[]` — URL paths in display order (persisted to `localStorage`)
- `hiddenNavs: string[]` — URL paths of hidden items (persisted to `localStorage`)
- `editMode: boolean` — whether edit mode is active
- `toggleEditMode`, `toggleNavVisibility`, `setNavOrder` actions

Initial state: all items visible, original order.

## Components Changed

- `SidebarContext.tsx` — add new state + localStorage persistence
- `Sidebar.tsx` — add edit toggle button, edit mode UI (drag handles, hide toggles), conditional rendering, DnD context
- `package.json` — add `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`

## Interaction

**Normal mode:**
- Renders only `visibleNavItems` in `navOrder`
- Hidden items are omitted entirely

**Edit mode:**
- All items shown (including hidden, greyed out)
- Drag handle (GripVertical) on left of each item
- Eye/EyeOff toggle on right of each item
- Items are sortable via drag-and-drop
- "Edit" button becomes "Done"
- State saved to localStorage on each change

## Non-Goals

- No new API endpoints (all config is client-side)
- No multi-user sync
- No animation for collapse/expand transitions (existing transition is sufficient)
