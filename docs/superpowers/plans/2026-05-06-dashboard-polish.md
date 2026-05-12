# Dashboard Polish Implementation Plan

**Goal:** Add count-up animation, hover preview cards, mini collaboration graph, live pulse, drag reorder, staggered entry.

**Architecture:** Pure frontend — `Dashboard.tsx` rewrite. No backend changes.

---

### Task: Rewrite Dashboard with all polish features

**File:** `web-ui/src/pages/Dashboard.tsx`

**Changes:**

1. **Count-up animation** — `useEffect` + `requestAnimationFrame` to animate metric numbers from 0 to target over 800ms
2. **Hover preview** — Use `HoverCard` from shadcn/ui to show agent details on hover over agent names
3. **Mini collaboration graph** — Fetch `/api/collaboration/graph`, render simple SVG with agent nodes and edge lines in a small card
4. **Live pulse indicator** — CSS `@keyframes pulse` on a small green dot in the footer, connected to LiveUpdatesContext WebSocket state
5. **Drag reorder** — Simple HTML5 drag-and-drop on cards, save order to localStorage key `dashboard-card-order`
6. **Stagger entry** — CSS `animation-delay` on each card based on index, using `@keyframes fadeInUp`

- [ ] **Step 1: Implement**

Read current `Dashboard.tsx`. Rewrite with all features above. Each feature should be a small self-contained addition.

- [ ] **Step 2: Verify**

```bash
npx tsc --noEmit && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/Dashboard.tsx
git commit -m "feat: dashboard polish — count-up, hover preview, mini collab graph, live pulse, drag reorder, stagger animation"
```
