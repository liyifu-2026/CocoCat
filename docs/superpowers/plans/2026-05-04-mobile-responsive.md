# Mobile Responsive Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add full mobile responsive support — bottom navigation bar, sidebar as overlay with swipe gestures, mobile-adapted layout

**Architecture:** Add `MOBILE_BREAKPOINT = 768` to SidebarContext. Layout switches between desktop (sidebar as width transition) and mobile (sidebar as fixed overlay). MobileBottomNav provides 5-key navigation bottom bar with scroll-hide behavior. Touch swipe gestures on mobile for sidebar open/close.

**Tech Stack:** React 19, Tailwind CSS v4, Radix UI

---

## File Structure

### New Files (1)
| File | Responsibility |
|------|---------------|
| `src/components/MobileBottomNav.tsx` | Fixed bottom nav bar with 5 items, scroll-hide, safe-area |

### Modified Files (4)
| File | Change |
|------|--------|
| `src/context/SidebarContext.tsx` | Add `isMobile` state with matchMedia listener |
| `src/components/Layout.tsx` | Mobile: sidebar as overlay + backdrop + swipe + MobileBottomNav |
| `src/components/Sidebar.tsx` | Accept `isMobile` prop for overlay mode |
| `src/index.css` | Ensure safe-area-inset support |

---

### Task 1: Update SidebarContext with mobile detection

**Files:**
- Modify: `src/context/SidebarContext.tsx`

- [ ] **Step 1: Add isMobile detection**

Read the current file, then update:

```tsx
import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

const MOBILE_BREAKPOINT = 768

interface SidebarContextValue {
  collapsed: boolean
  toggle: () => void
  isMobile: boolean
}

const SidebarContext = createContext<SidebarContextValue | null>(null)

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < MOBILE_BREAKPOINT)
  const [collapsed, setCollapsed] = useState(() => window.innerWidth < MOBILE_BREAKPOINT)

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const handler = (e: MediaQueryListEvent) => {
      setIsMobile(e.matches)
      if (e.matches) setCollapsed(true)
    }
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  const toggle = () => setCollapsed(c => !c)

  return (
    <SidebarContext.Provider value={{ collapsed, toggle, isMobile }}>
      {children}
    </SidebarContext.Provider>
  )
}

export function useSidebar() {
  const ctx = useContext(SidebarContext)
  if (!ctx) throw new Error("useSidebar must be used within SidebarProvider")
  return ctx
}
```

Key changes:
- Add `MOBILE_BREAKPOINT = 768`
- Add `isMobile` state derived from `matchMedia`
- On mobile: sidebar starts collapsed
- On breakpoint cross: auto-collapse/expand sidebar

- [ ] **Step 2: Verify compilation**

```bash
npx tsc --noEmit
```

---

### Task 2: Create MobileBottomNav

**Files:**
- Create: `src/components/MobileBottomNav.tsx`

- [ ] **Step 1: Create component**

```tsx
import { useNavigate, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useT } from "@/context/LanguageContext"
import {
  LayoutDashboard, MessageSquare, Users, Plus,
} from "lucide-react"

const navItems = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/chat", labelKey: "nav.chat", icon: MessageSquare },
  { to: "/agents", labelKey: "nav.agents", icon: Users },
]

interface MobileBottomNavProps {
  visible: boolean
}

export function MobileBottomNav({ visible }: MobileBottomNavProps) {
  const t = useT()
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <nav
      className={cn(
        "fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-background/80 backdrop-blur-lg transition-transform duration-200 md:hidden",
        visible ? "translate-y-0" : "translate-y-full",
      )}
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <div className="flex items-center justify-around h-14">
        {navItems.map(item => {
          const isActive = location.pathname.startsWith(item.to)
          return (
            <button
              key={item.to}
              onClick={() => navigate(item.to)}
              className={cn(
                "flex flex-col items-center gap-0.5 px-4 py-1 text-[10px] font-medium transition-colors",
                isActive ? "text-foreground" : "text-muted-foreground",
              )}
            >
              <item.icon className="size-5" />
              <span>{t(item.labelKey)}</span>
            </button>
          )
        })}
        <button
          onClick={() => navigate("/scenes")}
          className="flex flex-col items-center gap-0.5 px-4 py-1 text-[10px] font-medium text-muted-foreground"
        >
          <div className="size-10 rounded-full bg-primary flex items-center justify-center -mt-3">
            <Plus className="size-5 text-primary-foreground" />
          </div>
        </button>
      </div>
    </nav>
  )
}
```

---

### Task 3: Update Layout.tsx with mobile support

**Files:**
- Modify: `src/components/Layout.tsx`

- [ ] **Step 1: Add mobile sidebar overlay + swipe + bottom nav**

Read current Layout.tsx, then replace with:

```tsx
import { useRef, useCallback, useEffect, useState } from "react"
import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { SceneRail } from "./SceneRail"
import { BreadcrumbBar } from "./BreadcrumbBar"
import { PropertiesPanel } from "./PropertiesPanel"
import { CommandPalette } from "./CommandPalette"
import { NewAgentDialog } from "./NewAgentDialog"
import { NewSceneDialog } from "./NewSceneDialog"
import { NewGroupDialog } from "./NewGroupDialog"
import { ImportSceneDialog } from "./ImportSceneDialog"
import { KeyboardShortcuts } from "./KeyboardShortcuts"
import { MobileBottomNav } from "./MobileBottomNav"
import { useSidebar } from "@/context/SidebarContext"
import { cn } from "@/lib/utils"

export function Layout() {
  const { collapsed, toggle, isMobile } = useSidebar()
  const [navVisible, setNavVisible] = useState(true)
  const lastScrollRef = useRef(0)

  // Scroll-hide bottom nav
  useEffect(() => {
    if (!isMobile) return
    const mainEl = document.querySelector("main")
    if (!mainEl) return
    const onScroll = () => {
      const y = mainEl.scrollTop
      const delta = y - lastScrollRef.current
      if (delta > 8) setNavVisible(false)
      else if (delta < -8 || y <= 24) setNavVisible(true)
      lastScrollRef.current = y
    }
    mainEl.addEventListener("scroll", onScroll, { passive: true })
    return () => mainEl.removeEventListener("scroll", onScroll)
  }, [isMobile])

  // Swipe gesture for sidebar
  const touchStartRef = useRef<{ x: number; y: number } | null>(null)

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    touchStartRef.current = { x: e.touches[0]!.clientX, y: e.touches[0]!.clientY }
  }, [])

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    const start = touchStartRef.current
    if (!start) return
    touchStartRef.current = null
    const dx = e.changedTouches[0]!.clientX - start.x
    const dy = e.changedTouches[0]!.clientY - start.y
    if (Math.abs(dy) > 75) return
    if (start.x <= 30 && dx > 50) toggle()
    else if (dx < -50 && !collapsed) toggle()
  }, [toggle, collapsed])

  return (
    <div className="flex h-dvh" onTouchStart={isMobile ? handleTouchStart : undefined}
      onTouchEnd={isMobile ? handleTouchEnd : undefined}>
      <SceneRail />
      <Sidebar />
      {isMobile && !collapsed && (
        <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={toggle} />
      )}
      <div className={cn("flex flex-col flex-1 min-w-0", isMobile && "relative z-0")}>
        <BreadcrumbBar />
        <main className="flex-1 overflow-y-auto md:overflow-auto"
          style={isMobile ? { paddingBottom: "calc(5rem + env(safe-area-inset-bottom, 0px))" } : undefined}>
          <Outlet />
        </main>
      </div>
      <PropertiesPanel />
      <MobileBottomNav visible={navVisible} />
      <CommandPalette />
      <NewAgentDialog />
      <NewSceneDialog />
      <NewGroupDialog />
      <ImportSceneDialog />
      <KeyboardShortcuts />
    </div>
  )
}
```

---

### Task 4: Update Sidebar for overlay mode

**Files:**
- Modify: `src/components/Sidebar.tsx`

- [ ] **Step 1: Add overlay mode rendering**

At the top of the Sidebar component, after hooks, add:

```tsx
const { isMobile } = useSidebar()
```

Then wrap the existing sidebar `<aside>` with the desktop width transition OR mobile overlay.

Replace the current `<aside>` opening tag condition:

For mobile:
```tsx
{isMobile ? (
  <aside className={cn(
    "fixed inset-y-0 left-0 z-50 flex flex-col border-r border-border bg-sidebar transition-transform duration-100 ease-out w-56",
    collapsed ? "-translate-x-full" : "translate-x-0",
  )}>
    {/* existing sidebar content */}
  </aside>
) : (
  <aside className={cn(
    "flex flex-col border-r border-border bg-sidebar transition-[width] duration-100 ease-out overflow-hidden shrink-0",
    collapsed ? "w-0" : "w-56",
  )}>
    {/* existing sidebar content */}
  </aside>
)}
```

This preserves all existing sidebar content — the global nav sections, scene mode, and logout — unchanged.

---

### Task 5: Build verification

- [ ] **Step 1: Verify full build**

```bash
npm run build
```

Expected: Build succeeds.

- [ ] **Step 2: Quick visual check**

```bash
npm run dev
```

Open on mobile viewport (Chrome DevTools < 768px). Verify:
- Sidebar hidden by default
- Swipe from left edge opens sidebar
- Backdrop overlay appears
- Bottom nav visible, scrolls away on scroll down
- Desktop unaffected
