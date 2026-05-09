# CocoCat UI → Paperclip Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) for tracking.

**Goal:** Align CocoCat's web-ui with Paperclip's UI architecture — three-column layout, new interactive components, visual design system

**Architecture:** React SPA with new context providers (Breadcrumb, Panel, Dialog, LiveUpdates), three-column layout (Rail + Sidebar + Main + PropertiesPanel), global command palette, and Paperclip-aligned CSS design tokens

**Tech Stack:** React 19, TypeScript 6, Vite 8, Tailwind CSS v4, shadcn/ui (New York), Radix UI, cmdk, Lucide icons

---

## File Structure

### New Files (8)
| File | Responsibility |
|------|---------------|
| `src/context/BreadcrumbContext.tsx` | Breadcrumb state + auto document.title |
| `src/context/PanelContext.tsx` | Properties panel visibility + content |
| `src/context/DialogContext.tsx` | Global dialog state (split context pattern) |
| `src/context/LiveUpdatesContext.tsx` | WebSocket real-time updates |
| `src/components/CompanyRail.tsx` | Left vertical navigation rail (44px) |
| `src/components/BreadcrumbBar.tsx` | Top breadcrumb toolbar |
| `src/components/PropertiesPanel.tsx` | Right slide-in properties panel (320px) |
| `src/components/CommandPalette.tsx` | Cmd+K global command palette |

### Modified Files (5)
| File | Change |
|------|--------|
| `package.json` | Add `@tailwindcss/typography` devDependency |
| `src/index.css` | Add chart vars, sidebar-primary, animations, scrollbar, mobile styles |
| `src/main.tsx` | Wrap App with new providers |
| `src/components/Layout.tsx` | Restructure to three-column layout |
| `src/components/Sidebar.tsx` | Expand to text+icon 220px sidebar |

### Per-Page Modifications (14 files)
| File | Change |
|------|--------|
| `src/pages/*.tsx` | Each page adds `setBreadcrumbs()` + optional panel content |

---

### Task 1: CSS Design System + Dependencies

**Files:**
- Modify: `web-ui/package.json`
- Modify: `web-ui/src/index.css`

- [ ] **Step 1: Add @tailwindcss/typography dependency**

Run:
```bash
pnpm add -D @tailwindcss/typography
```

Expected: package.json updated with new devDependency.

- [ ] **Step 2: Replace index.css with Paperclip-aligned design system**

Replace `web-ui/src/index.css` entirely:

```css
@import "tailwindcss";
@plugin "@tailwindcss/typography";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-destructive-foreground: var(--destructive-foreground);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --color-chart-1: var(--chart-1);
  --color-chart-2: var(--chart-2);
  --color-chart-3: var(--chart-3);
  --color-chart-4: var(--chart-4);
  --color-chart-5: var(--chart-5);
  --color-sidebar: var(--sidebar);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar-primary: var(--sidebar-primary);
  --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
  --color-sidebar-accent: var(--sidebar-accent);
  --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-ring: var(--sidebar-ring);
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0px;
  --radius-xl: 0px;
}

:root {
  color-scheme: light;
  --radius: 0;
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --secondary: oklch(0.97 0 0);
  --secondary-foreground: oklch(0.205 0 0);
  --muted: oklch(0.97 0 0);
  --muted-foreground: oklch(0.556 0 0);
  --accent: oklch(0.97 0 0);
  --accent-foreground: oklch(0.205 0 0);
  --destructive: oklch(0.577 0.245 27.325);
  --destructive-foreground: oklch(0.577 0.245 27.325);
  --border: oklch(0.922 0 0);
  --input: oklch(0.922 0 0);
  --ring: oklch(0.708 0 0);
  --chart-1: oklch(0.646 0.222 41.116);
  --chart-2: oklch(0.6 0.118 184.704);
  --chart-3: oklch(0.398 0.07 227.392);
  --chart-4: oklch(0.828 0.189 84.429);
  --chart-5: oklch(0.769 0.188 70.08);
  --sidebar: oklch(0.985 0 0);
  --sidebar-foreground: oklch(0.145 0 0);
  --sidebar-primary: oklch(0.205 0 0);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.97 0 0);
  --sidebar-accent-foreground: oklch(0.205 0 0);
  --sidebar-border: oklch(0.922 0 0);
  --sidebar-ring: oklch(0.708 0 0);
}

.dark {
  color-scheme: dark;
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --card: oklch(0.205 0 0);
  --card-foreground: oklch(0.985 0 0);
  --popover: oklch(0.205 0 0);
  --popover-foreground: oklch(0.985 0 0);
  --primary: oklch(0.985 0 0);
  --primary-foreground: oklch(0.205 0 0);
  --secondary: oklch(0.269 0 0);
  --secondary-foreground: oklch(0.985 0 0);
  --muted: oklch(0.269 0 0);
  --muted-foreground: oklch(0.708 0 0);
  --accent: oklch(0.269 0 0);
  --accent-foreground: oklch(0.985 0 0);
  --destructive: oklch(0.637 0.237 25.331);
  --destructive-foreground: oklch(0.985 0 0);
  --border: oklch(0.269 0 0);
  --input: oklch(0.269 0 0);
  --ring: oklch(0.439 0 0);
  --chart-1: oklch(0.488 0.243 264.376);
  --chart-2: oklch(0.696 0.17 162.48);
  --chart-3: oklch(0.769 0.188 70.08);
  --chart-4: oklch(0.627 0.265 303.9);
  --chart-5: oklch(0.645 0.246 16.439);
  --sidebar: oklch(0.145 0 0);
  --sidebar-foreground: oklch(0.985 0 0);
  --sidebar-primary: oklch(0.488 0.243 264.376);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.269 0 0);
  --sidebar-accent-foreground: oklch(0.985 0 0);
  --sidebar-border: oklch(0.269 0 0);
  --sidebar-ring: oklch(0.439 0 0);
}

@layer base {
  * {
    @apply border-border;
  }
  html {
    height: 100%;
    -webkit-tap-highlight-color: color-mix(in oklab, var(--foreground) 20%, transparent);
  }
  body {
    @apply bg-background text-foreground antialiased;
    height: 100%;
    overflow: hidden;
  }
  h1, h2, h3 {
    text-wrap: balance;
  }
  a, button, [role="button"], input, select, textarea, label {
    touch-action: manipulation;
  }
  #root {
    height: 100%;
  }
}

@media (pointer: coarse) {
  button, [role="button"], input, select, textarea, [data-slot="select-trigger"] {
    min-height: 44px;
  }
  [data-slot="toggle"] {
    min-height: 0;
  }
}

.dark {
  color-scheme: dark;
}

.dark *::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.dark *::-webkit-scrollbar-track {
  background: oklch(0.205 0 0);
}
.dark *::-webkit-scrollbar-thumb {
  background: oklch(0.4 0 0);
  border-radius: 4px;
}
.dark *::-webkit-scrollbar-thumb:hover {
  background: oklch(0.5 0 0);
}

.scrollbar-auto-hide::-webkit-scrollbar {
  width: 8px !important;
  background: transparent !important;
}
.scrollbar-auto-hide::-webkit-scrollbar-track {
  background: transparent !important;
}
.scrollbar-auto-hide::-webkit-scrollbar-thumb {
  background: transparent !important;
}
.scrollbar-auto-hide:hover::-webkit-scrollbar-track {
  background: oklch(0.92 0 0) !important;
}
.scrollbar-auto-hide:hover::-webkit-scrollbar-thumb {
  background: oklch(0.7 0 0) !important;
}
.scrollbar-auto-hide:hover::-webkit-scrollbar-thumb:hover {
  background: oklch(0.6 0 0) !important;
}
.dark .scrollbar-auto-hide:hover::-webkit-scrollbar-track {
  background: oklch(0.205 0 0) !important;
}
.dark .scrollbar-auto-hide:hover::-webkit-scrollbar-thumb {
  background: oklch(0.4 0 0) !important;
}
.dark .scrollbar-auto-hide:hover::-webkit-scrollbar-thumb:hover {
  background: oklch(0.5 0 0) !important;
}

[data-slot="dialog-content"] {
  transition: max-width 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes dashboard-activity-enter {
  0% { opacity: 0; transform: translateY(-14px) scale(0.985); filter: blur(4px); }
  62% { opacity: 1; transform: translateY(2px) scale(1.002); filter: blur(0); }
  100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
}
@keyframes dashboard-activity-highlight {
  0% { box-shadow: inset 2px 0 0 var(--primary); background-color: color-mix(in oklab, var(--accent) 55%, transparent); }
  100% { box-shadow: inset 0 0 0 transparent; background-color: transparent; }
}
.activity-row-enter {
  animation: dashboard-activity-enter 520ms cubic-bezier(0.16, 1, 0.3, 1), dashboard-activity-highlight 920ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes cot-line-slide-in {
  from { transform: translateY(100%); }
  to   { transform: translateY(0); }
}
@keyframes cot-line-slide-out {
  from { transform: translateY(0); }
  to   { transform: translateY(-100%); }
}
.cot-line-enter { animation: cot-line-slide-in 300ms cubic-bezier(0.4, 0, 0.2, 1) both; }
.cot-line-exit  { animation: cot-line-slide-out 300ms cubic-bezier(0.4, 0, 0.2, 1) forwards; }

@keyframes shimmer-text-slide {
  0% { background-position: 100% center; }
  60% { background-position: 0% center; }
  100% { background-position: 0% center; }
}
.shimmer-text {
  --shimmer-base: var(--foreground);
  --shimmer-highlight: color-mix(in oklch, var(--foreground) 35%, transparent);
  background: linear-gradient(90deg, var(--shimmer-base) 0%, var(--shimmer-base) 40%, var(--shimmer-highlight) 50%, var(--shimmer-base) 60%, var(--shimmer-base) 100%);
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer-text-slide 2.5s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .activity-row-enter, .cot-line-enter, .cot-line-exit, .shimmer-text { animation: none; }
  .shimmer-text { -webkit-text-fill-color: unset; background: none; }
}
```

- [ ] **Step 3: Verify CSS compiles**

Run:
```bash
pnpm build
```

Expected: Build succeeds, no CSS errors.

---

### Task 2: Context Providers

**Files:**
- Create: `web-ui/src/context/BreadcrumbContext.tsx`
- Create: `web-ui/src/context/PanelContext.tsx`
- Create: `web-ui/src/context/DialogContext.tsx`
- Create: `web-ui/src/context/LiveUpdatesContext.tsx`

- [ ] **Step 1: Create BreadcrumbContext**

```tsx
import { createContext, useContext, useState, useCallback, type ReactNode } from "react"

export interface Breadcrumb {
  label: string
  href?: string
}

interface BreadcrumbContextValue {
  breadcrumbs: Breadcrumb[]
  setBreadcrumbs: (crumbs: Breadcrumb[]) => void
}

const BreadcrumbContext = createContext<BreadcrumbContextValue | null>(null)

export function BreadcrumbProvider({ children }: { children: ReactNode }) {
  const [breadcrumbs, setBreadcrumbsState] = useState<Breadcrumb[]>([])

  const setBreadcrumbs = useCallback((crumbs: Breadcrumb[]) => {
    setBreadcrumbsState(crumbs)
    document.title = crumbs.length > 0
      ? `${crumbs.map(c => c.label).join(" · ")} · CocoCat`
      : "CocoCat"
  }, [])

  return (
    <BreadcrumbContext.Provider value={{ breadcrumbs, setBreadcrumbs }}>
      {children}
    </BreadcrumbContext.Provider>
  )
}

export function useBreadcrumbs() {
  const ctx = useContext(BreadcrumbContext)
  if (!ctx) throw new Error("useBreadcrumbs must be used within BreadcrumbProvider")
  return ctx
}
```

- [ ] **Step 2: Create PanelContext**

```tsx
import { createContext, useContext, useState, useCallback, type ReactNode } from "react"

interface PanelContextValue {
  content: ReactNode | null
  visible: boolean
  openPanel: (content: ReactNode) => void
  closePanel: () => void
  togglePanel: () => void
}

const PanelContext = createContext<PanelContextValue | null>(null)

export function PanelProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<ReactNode | null>(null)
  const [visible, setVisible] = useState(true)

  const openPanel = useCallback((newContent: ReactNode) => {
    setContent(newContent)
    setVisible(true)
  }, [])

  const closePanel = useCallback(() => {
    setVisible(false)
  }, [])

  const togglePanel = useCallback(() => {
    setVisible(v => !v)
  }, [])

  return (
    <PanelContext.Provider value={{ content, visible, openPanel, closePanel, togglePanel }}>
      {children}
    </PanelContext.Provider>
  )
}

export function usePanel() {
  const ctx = useContext(PanelContext)
  if (!ctx) throw new Error("usePanel must be used within PanelProvider")
  return ctx
}
```

- [ ] **Step 3: Create DialogContext**

```tsx
import { createContext, useContext, useState, useCallback, type ReactNode } from "react"

interface DialogState {
  newAgentOpen: boolean
  newSceneOpen: boolean
  newGroupOpen: boolean
}

interface DialogActions {
  openNewAgent: () => void
  closeNewAgent: () => void
  openNewScene: () => void
  closeNewScene: () => void
  openNewGroup: () => void
  closeNewGroup: () => void
}

const DialogStateContext = createContext<DialogState | null>(null)
const DialogActionsContext = createContext<DialogActions | null>(null)

export function DialogProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DialogState>({
    newAgentOpen: false,
    newSceneOpen: false,
    newGroupOpen: false,
  })

  const actions: DialogActions = {
    openNewAgent: () => setState(s => ({ ...s, newAgentOpen: true })),
    closeNewAgent: () => setState(s => ({ ...s, newAgentOpen: false })),
    openNewScene: () => setState(s => ({ ...s, newSceneOpen: true })),
    closeNewScene: () => setState(s => ({ ...s, newSceneOpen: false })),
    openNewGroup: () => setState(s => ({ ...s, newGroupOpen: true })),
    closeNewGroup: () => setState(s => ({ ...s, newGroupOpen: false })),
  }

  return (
    <DialogStateContext.Provider value={state}>
      <DialogActionsContext.Provider value={actions}>
        {children}
      </DialogActionsContext.Provider>
    </DialogStateContext.Provider>
  )
}

export function useDialogState() {
  const ctx = useContext(DialogStateContext)
  if (!ctx) throw new Error("useDialogState must be used within DialogProvider")
  return ctx
}

export function useDialogActions() {
  const ctx = useContext(DialogActionsContext)
  if (!ctx) throw new Error("useDialogActions must be used within DialogProvider")
  return ctx
}

export function useDialog() {
  return { ...useDialogState(), ...useDialogActions() }
}
```

- [ ] **Step 4: Create LiveUpdatesContext**

```tsx
import { createContext, useContext, useEffect, useRef, useCallback, type ReactNode } from "react"
import { useQueryClient } from "@tanstack/react-query"

interface LiveUpdatesValue {}

const LiveUpdatesContext = createContext<LiveUpdatesValue | null>(null)

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000]

export function LiveUpdatesProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectIndexRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:"
    const ws = new WebSocket(`${protocol}//${location.host}/ws`)
    wsRef.current = ws

    ws.onopen = () => {
      reconnectIndexRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        switch (data.type) {
          case "agent.status":
            queryClient.invalidateQueries({ queryKey: ["agents"] })
            break
          case "message.new":
            queryClient.invalidateQueries({ queryKey: ["chat"] })
            break
          case "dispatch.update":
            queryClient.invalidateQueries({ queryKey: ["dispatches"] })
            break
        }
      } catch {}
    }

    ws.onclose = () => {
      const delay = RECONNECT_DELAYS[Math.min(reconnectIndexRef.current, RECONNECT_DELAYS.length - 1)]
      reconnectIndexRef.current++
      reconnectTimerRef.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [queryClient])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      clearTimeout(reconnectTimerRef.current)
    }
  }, [connect])

  return (
    <LiveUpdatesContext.Provider value={{}}>
      {children}
    </LiveUpdatesContext.Provider>
  )
}

export function useLiveUpdates() {
  const ctx = useContext(LiveUpdatesContext)
  if (!ctx) throw new Error("useLiveUpdates must be used within LiveUpdatesProvider")
  return ctx
}
```

- [ ] **Step 5: Verify TypeScript compilation**

```bash
pnpm build
```

Expected: Build succeeds (may trigger errors if imports are missing in main.tsx — verify type-only for now).

---

### Task 3: CompanyRail Component

**Files:**
- Create: `web-ui/src/components/CompanyRail.tsx`

- [ ] **Step 1: Create CompanyRail component**

```tsx
import { useAuth } from "@/context/AuthContext"
import { LogOut, LayoutDashboard } from "lucide-react"
import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"

const railItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
]

export function CompanyRail() {
  const { logout } = useAuth()

  return (
    <aside className="w-11 shrink-0 border-r border-border bg-sidebar flex flex-col items-center py-2 gap-2">
      <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center text-primary-foreground text-xs font-bold">
        C
      </div>
      <nav className="flex-1 flex flex-col items-center gap-1">
        {railItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "w-7 h-7 rounded-md flex items-center justify-center transition-colors",
                isActive ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent",
              )
            }
            title={item.label}
          >
            <item.icon className="size-4" />
          </NavLink>
        ))}
      </nav>
      <button
        onClick={logout}
        className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-sidebar-accent hover:text-destructive transition-colors"
        title="退出登录"
      >
        <LogOut className="size-4" />
      </button>
    </aside>
  )
}
```

---

### Task 4: Sidebar Rewrite

**Files:**
- Modify: `web-ui/src/components/Sidebar.tsx`

- [ ] **Step 1: Replace sidebar with expanded text+icon version**

Replace entire `Sidebar.tsx`:

```tsx
import { NavLink, useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useAuth } from "@/context/AuthContext"
import { useSidebar } from "@/context/SidebarContext"
import {
  LayoutDashboard, Users, FolderKanban, Settings, BookOpen, Mail, BarChart3,
  UserPlus, MessageSquare, Calendar, GitBranch, PanelLeftClose, PanelLeft, Search, LogOut,
} from "lucide-react"
import { Button } from "@/components/ui/button"

const navSections = [
  {
    label: null,
    items: [
      { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ],
  },
  {
    label: "Workspace",
    items: [
      { to: "/agents", label: "Agents", icon: Users },
      { to: "/scenes", label: "Scenes", icon: FolderKanban },
      { to: "/chat", label: "Chat", icon: MessageSquare },
      { to: "/knowledge", label: "Knowledge", icon: BookOpen },
    ],
  },
  {
    label: "Management",
    items: [
      { to: "/hiring", label: "Hiring", icon: UserPlus },
      { to: "/mailbox", label: "Mailbox", icon: Mail },
      { to: "/schedule", label: "Schedule", icon: Calendar },
      { to: "/usage", label: "Usage", icon: BarChart3 },
      { to: "/collaboration", label: "协作图", icon: GitBranch },
    ],
  },
]

export function Sidebar() {
  const { collapsed, toggle } = useSidebar()
  const { logout } = useAuth()
  const navigate = useNavigate()

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-sidebar transition-[width] duration-100 ease-out overflow-hidden shrink-0",
        collapsed ? "w-0" : "w-56",
      )}
    >
      <div className="flex h-12 items-center justify-between border-b border-sidebar-border px-4 shrink-0">
        <span className="font-semibold text-sm text-sidebar-foreground">CocoCat</span>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon-xs" onClick={() => navigate("/dashboard")} className="text-sidebar-foreground">
            <Search className="size-4" />
          </Button>
          <Button variant="ghost" size="icon-xs" onClick={toggle} className="text-sidebar-foreground">
            {collapsed ? <PanelLeft className="size-4" /> : <PanelLeftClose className="size-4" />}
          </Button>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto scrollbar-auto-hide px-2 py-3 space-y-4">
        {navSections.map(section => (
          <div key={section.label ?? "top"}>
            {section.label && (
              <div className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {section.label}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors",
                      isActive
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground hover:bg-sidebar-accent",
                    )
                  }
                >
                  <item.icon className="size-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-2 shrink-0">
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-1.5 text-[13px] font-medium text-muted-foreground hover:text-destructive hover:bg-sidebar-accent transition-colors"
        >
          <LogOut className="size-4 shrink-0" />
          <span>退出登录</span>
        </button>
      </div>
    </aside>
  )
}
```

Remove the now-unused `LogOut` import from the original — it's still used. Remove `PanelLeftClose`, `PanelLeft` — still used. Keep only actually used imports.

---

### Task 5: BreadcrumbBar Component

**Files:**
- Create: `web-ui/src/components/BreadcrumbBar.tsx`

- [ ] **Step 1: Create BreadcrumbBar**

```tsx
import { useBreadcrumbs } from "@/context/BreadcrumbContext"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

export function BreadcrumbBar() {
  const { breadcrumbs } = useBreadcrumbs()

  if (breadcrumbs.length === 0) {
    return (
      <div className="flex h-12 items-center justify-end border-b border-border px-4 shrink-0">
        <button className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-accent transition-colors text-xs">
          ⌘K
        </button>
      </div>
    )
  }

  if (breadcrumbs.length === 1) {
    return (
      <div className="flex h-12 items-center justify-between border-b border-border px-4 shrink-0">
        <h1 className="text-sm font-semibold uppercase tracking-wider text-foreground">
          {breadcrumbs[0].label}
        </h1>
        <button className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-accent transition-colors text-xs">
          ⌘K
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-12 items-center justify-between border-b border-border px-4 shrink-0">
      <Breadcrumb>
        <BreadcrumbList>
          {breadcrumbs.map((crumb, i) => (
            <BreadcrumbItem key={i}>
              {i < breadcrumbs.length - 1 ? (
                <>
                  <BreadcrumbLink href={crumb.href}>{crumb.label}</BreadcrumbLink>
                  <BreadcrumbSeparator />
                </>
              ) : (
                <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
      <button className="w-7 h-7 rounded-md flex items-center justify-center text-muted-foreground hover:bg-accent transition-colors text-xs">
        ⌘K
      </button>
    </div>
  )
}
```

---

### Task 6: PropertiesPanel Component

**Files:**
- Create: `web-ui/src/components/PropertiesPanel.tsx`

- [ ] **Step 1: Create PropertiesPanel**

```tsx
import { usePanel } from "@/context/PanelContext"
import { ScrollArea } from "@/components/ui/scroll-area"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export function PropertiesPanel() {
  const { content, visible, closePanel } = usePanel()

  if (!content) return null

  return (
    <aside
      className={cn(
        "hidden md:flex border-l border-border bg-card flex-col shrink-0 overflow-hidden h-full transition-[width,opacity] duration-200 ease-in-out",
        visible ? "w-80 opacity-100" : "w-0 opacity-0",
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-4 h-12 shrink-0">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Properties</span>
        <button
          onClick={closePanel}
          className="w-6 h-6 rounded flex items-center justify-center text-muted-foreground hover:bg-accent transition-colors"
        >
          <X className="size-3.5" />
        </button>
      </div>
      <ScrollArea className="flex-1 p-4">
        {content}
      </ScrollArea>
    </aside>
  )
}
```

---

### Task 7: CommandPalette Component

**Files:**
- Create: `web-ui/src/components/CommandPalette.tsx`

- [ ] **Step 1: Create CommandPalette**

```tsx
import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import { useDialogActions } from "@/context/DialogContext"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { Users, FolderKanban, LayoutDashboard, Plus, MessageSquare, BookOpen, UserPlus, Mail, BarChart3, Calendar, GitBranch, Settings } from "lucide-react"

const pageItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/agents", label: "Agents", icon: Users },
  { to: "/scenes", label: "Scenes", icon: FolderKanban },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
  { to: "/hiring", label: "Hiring", icon: UserPlus },
  { to: "/mailbox", label: "Mailbox", icon: Mail },
  { to: "/usage", label: "Usage", icon: BarChart3 },
  { to: "/schedule", label: "Schedule", icon: Calendar },
  { to: "/collaboration", label: "协作图", icon: GitBranch },
  { to: "/settings", label: "Settings", icon: Settings },
]

interface Agent {
  id: string
  name: string
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const navigate = useNavigate()
  const { openNewAgent, openNewScene } = useDialogActions()

  const { data: agents = [] } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: () => api.get("/agents"),
    enabled: open,
  })

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen(o => !o)
      }
    }
    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [])

  const runCommand = (command: () => void) => {
    setOpen(false)
    command()
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search..." value={query} onValueChange={setQuery} />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Actions">
          <CommandItem onSelect={() => runCommand(openNewAgent)}>
            <Plus className="mr-2 h-4 w-4" />
            <span>Create new Agent</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(openNewScene)}>
            <Plus className="mr-2 h-4 w-4" />
            <span>Create new Scene</span>
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Pages">
          {pageItems.map(item => (
            <CommandItem key={item.to} onSelect={() => runCommand(() => navigate(item.to))}>
              <item.icon className="mr-2 h-4 w-4" />
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        {agents.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Agents">
              {agents.map((agent: Agent) => (
                <CommandItem key={agent.id} onSelect={() => runCommand(() => navigate(`/agents/${agent.id}`))}>
                  <Users className="mr-2 h-4 w-4" />
                  <span>{agent.name}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  )
}
```

---

### Task 8: Layout.tsx Restructure

**Files:**
- Modify: `web-ui/src/components/Layout.tsx`

- [ ] **Step 1: Rewrite Layout with three-column structure**

```tsx
import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { CompanyRail } from "./CompanyRail"
import { BreadcrumbBar } from "./BreadcrumbBar"
import { PropertiesPanel } from "./PropertiesPanel"
import { CommandPalette } from "./CommandPalette"
import { TooltipProvider } from "@/components/ui/tooltip"

export function Layout() {
  return (
    <TooltipProvider delayDuration={0}>
      <div className="flex h-dvh">
        <CompanyRail />
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0">
          <BreadcrumbBar />
          <main className="flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
        <PropertiesPanel />
      </div>
      <CommandPalette />
    </TooltipProvider>
  )
}
```

---

### Task 9: main.tsx Provider Integration

**Files:**
- Modify: `web-ui/src/main.tsx`

- [ ] **Step 1: Add new providers to main.tsx**

```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ThemeProvider } from "@/context/ThemeContext"
import { SidebarProvider } from "@/context/SidebarContext"
import { AuthProvider } from "@/context/AuthContext"
import { BreadcrumbProvider } from "@/context/BreadcrumbContext"
import { PanelProvider } from "@/context/PanelContext"
import { DialogProvider } from "@/context/DialogContext"
import { LiveUpdatesProvider } from "@/context/LiveUpdatesContext"
import { Toaster } from "sonner"
import App from "./App"
import "./index.css"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <SidebarProvider>
            <BreadcrumbProvider>
              <PanelProvider>
                <DialogProvider>
                  <LiveUpdatesProvider>
                    <App />
                    <Toaster richColors closeButton position="top-right" />
                  </LiveUpdatesProvider>
                </DialogProvider>
              </PanelProvider>
            </BreadcrumbProvider>
          </SidebarProvider>
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
```

---

### Task 10: Per-Page Breadcrumb + Panel Integration

**Files:**
- Modify: `web-ui/src/pages/Dashboard.tsx`
- Modify: `web-ui/src/pages/Agents.tsx`
- Modify: `web-ui/src/pages/AgentDetail.tsx`
- Modify: `web-ui/src/pages/Scenes.tsx`
- Modify: `web-ui/src/pages/SceneDetail.tsx`
- Modify: `web-ui/src/pages/Chat.tsx`
- Modify: `web-ui/src/pages/Knowledge.tsx`
- Modify: `web-ui/src/pages/KnowledgeDetail.tsx`
- Modify: `web-ui/src/pages/Hiring.tsx`
- Modify: `web-ui/src/pages/Mailbox.tsx`
- Modify: `web-ui/src/pages/TokenUsage.tsx`
- Modify: `web-ui/src/pages/Schedule.tsx`
- Modify: `web-ui/src/pages/Collaboration.tsx`
- Modify: `web-ui/src/pages/Settings.tsx`

- [ ] **Step 1: Add useBreadcrumbs to each page**

For each page, add at the top of the component after hooks:

```tsx
import { useBreadcrumbs } from "@/context/BreadcrumbContext"
import { usePanel } from "@/context/PanelContext"

export function Dashboard() {
  const { setBreadcrumbs } = useBreadcrumbs()
  const { openPanel } = usePanel()

  useEffect(() => {
    setBreadcrumbs([{ label: "Dashboard" }])
  }, [setBreadcrumbs])

  // ... rest of component
}
```

Breadcrumb definitions per page:

| Page | Breadcrumbs |
|------|------------|
| Dashboard | `[{ label: "Dashboard" }]` |
| Agents | `[{ label: "Agents" }]` |
| AgentDetail | `[{ label: "Agents", href: "/agents" }, { label: agent.name }]` |
| Scenes | `[{ label: "Scenes" }]` |
| SceneDetail | `[{ label: "Scenes", href: "/scenes" }, { label: scene.name }]` |
| Chat | `[{ label: "Chat" }]` |
| Knowledge | `[{ label: "Knowledge" }]` |
| KnowledgeDetail | `[{ label: "Knowledge", href: "/knowledge" }, { label: kbName }]` |
| Hiring | `[{ label: "Hiring" }]` |
| Mailbox | `[{ label: "Mailbox" }]` |
| Usage | `[{ label: "Usage" }]` |
| Schedule | `[{ label: "Schedule" }]` |
| Collaboration | `[{ label: "Collaboration" }]` |
| Settings | `[{ label: "Settings" }]` |

- [ ] **Step 2: Add properties panel content to detail pages**

For AgentDetail and SceneDetail, add panel content:

```tsx
// Inside AgentDetail, after loading agent data:
useEffect(() => {
  if (agent) {
    openPanel(
      <div className="space-y-4">
        <div>
          <div className="text-xs text-muted-foreground mb-1">Status</div>
          <div className="text-sm font-medium">{agent.status ?? "Unknown"}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">ID</div>
          <div className="text-sm font-medium">{agent.id}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Scene</div>
          <div className="text-sm font-medium">{agent.scene ?? "None"}</div>
        </div>
      </div>
    )
  }
}, [agent, openPanel])
```

---

### Task 11: Build Verification

- [ ] **Step 1: Run full build**

```bash
pnpm build
```

Expected: Build succeeds. If TypeScript errors occur, fix them (likely missing imports or unused variables).

- [ ] **Step 2: Run lint**

```bash
pnpm lint
```

Expected: No errors.
