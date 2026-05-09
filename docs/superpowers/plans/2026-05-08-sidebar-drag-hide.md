# Sidebar Drag & Hide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add drag-to-reorder and per-item hide/show to sidebar navigation

**Architecture:** Extend `SidebarContext` with order/visibility/edit-mode state persisted to `localStorage`. Add `@dnd-kit` for sortable drag-and-drop in edit mode. Conditionally render visible items in normal mode.

**Tech Stack:** React 19, TypeScript, Tailwind v4, shadcn/ui, @dnd-kit, lucide-react

---

### Task 1: Install @dnd-kit dependencies

**Files:**
- Modify: `web-ui/package.json`

- [ ] **Install @dnd-kit packages**

Run: `npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`

Workdir: `/home/leaif/CocoCat/web-ui`

- [ ] **Verify install**

Run: `node -e "require('@dnd-kit/core'); require('@dnd-kit/sortable'); require('@dnd-kit/utilities'); console.log('ok')"`

Expected output: `ok`

---

### Task 2: Extend SidebarContext with order/visibility/edit state + localStorage

**Files:**
- Modify: `web-ui/src/context/SidebarContext.tsx`

**New state in SidebarContext:**
- `navOrder: string[]` — ordered list of route paths (e.g. `["/dashboard", "/chat", ...]`)
- `hiddenNavs: string[]` — list of hidden route paths
- `editMode: boolean` — edit mode active flag
- `toggleEditMode: () => void`
- `toggleNavVisibility: (path: string) => void`
- `setNavOrder: (order: string[]) => void`
- `availablePaths: string[]` — the 12 canonical paths from navItems (constant)

**Persistence:**
- Key: `cococat-sidebar-nav-config`
- Shape: `{ order: string[], hidden: string[] }`
- Load on mount, save on every change

**Initial values (first load / no localStorage):**
- `order`: all 12 paths in original order
- `hidden`: empty array

- [ ] **Write the updated SidebarContext**

Replace `web-ui/src/context/SidebarContext.tsx`:

```tsx
import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react"

const DEFAULT_PATHS = [
  "/dashboard", "/chat", "/agents", "/scenes", "/hiring", "/mailbox",
  "/usage", "/schedule", "/collaboration", "/knowledge", "/skills", "/settings",
]

const STORAGE_KEY = "cococat-sidebar-nav-config"

function loadConfig(): { order: string[]; hidden: string[] } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return { order: [...DEFAULT_PATHS], hidden: [] }
}

function saveConfig(order: string[], hidden: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ order, hidden }))
}

const SidebarContext = createContext<{
  collapsed: boolean
  toggle: () => void
  navOrder: string[]
  hiddenNavs: string[]
  editMode: boolean
  toggleEditMode: () => void
  toggleNavVisibility: (path: string) => void
  setNavOrder: (order: string[]) => void
  availablePaths: string[]
} | null>(null)

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const toggle = () => setCollapsed(c => !c)

  const [config, setConfig] = useState(loadConfig)
  const [editMode, setEditMode] = useState(false)

  useEffect(() => {
    saveConfig(config.order, config.hidden)
  }, [config])

  const toggleEditMode = useCallback(() => setEditMode(e => !e), [])
  const toggleNavVisibility = useCallback((path: string) => {
    setConfig(prev => {
      const hidden = prev.hidden.includes(path)
        ? prev.hidden.filter(p => p !== path)
        : [...prev.hidden, path]
      return { ...prev, hidden }
    })
  }, [])
  const setNavOrder = useCallback((order: string[]) => {
    setConfig(prev => ({ ...prev, order }))
  }, [])

  return (
    <SidebarContext.Provider value={{
      collapsed, toggle,
      navOrder: config.order,
      hiddenNavs: config.hidden,
      editMode, toggleEditMode, toggleNavVisibility, setNavOrder,
      availablePaths: DEFAULT_PATHS,
    }}>
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

---

### Task 3: Update Sidebar component with edit mode, drag-and-drop, hide toggles

**Files:**
- Modify: `web-ui/src/components/Sidebar.tsx`

**Changes:**
1. Add edit mode toggle button at sidebar bottom (next to logout)
2. In edit mode: all items shown, drag handle (GripVertical), hide toggle (Eye/EyeOff), greyed hidden items
3. In normal mode: only visible items rendered, in navOrder
4. Wrap nav items with @dnd-kit SortableContext when in edit mode
5. Add DndContext + closestCenter collision detection

- [ ] **Write the updated Sidebar**

Replace `web-ui/src/components/Sidebar.tsx`:

```tsx
import { useState } from "react"
import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useSidebar } from "@/context/SidebarContext"
import { useAuth } from "@/context/AuthContext"
import { useT } from "@/context/LanguageContext"
import {
  LayoutDashboard, Users, FolderKanban, Settings, BookOpen, Mail, BarChart3,
  UserPlus, MessageSquare, Calendar, GitBranch, Wrench,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { PanelLeftClose, PanelLeft, LogOut, Pencil, GripVertical, Eye, EyeOff } from "lucide-react"
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext, verticalListSortingStrategy, useSortable,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"

interface NavItem {
  to: string
  labelKey: string
  icon: React.ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/chat", labelKey: "nav.chat", icon: MessageSquare },
  { to: "/agents", labelKey: "nav.agents", icon: Users },
  { to: "/scenes", labelKey: "nav.scenes", icon: FolderKanban },
  { to: "/hiring", labelKey: "nav.hiring", icon: UserPlus },
  { to: "/mailbox", labelKey: "nav.mailbox", icon: Mail },
  { to: "/usage", labelKey: "nav.usage", icon: BarChart3 },
  { to: "/schedule", labelKey: "nav.schedule", icon: Calendar },
  { to: "/collaboration", labelKey: "nav.collaboration", icon: GitBranch },
  { to: "/knowledge", labelKey: "nav.knowledge", icon: BookOpen },
  { to: "/skills", labelKey: "nav.skills", icon: Wrench },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
]

const itemMap = new Map(navItems.map(i => [i.to, i]))

function SortableNavItem({
  item, collapsed, hidden, onToggleHide, t,
}: {
  item: NavItem
  collapsed: boolean
  hidden: boolean
  onToggleHide: () => void
  t: (key: string) => string
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.to })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center rounded-md transition-colors",
        isDragging && "opacity-50",
        hidden && "opacity-40",
      )}
    >
      <span
        {...attributes}
        {...listeners}
        className="flex items-center justify-center w-6 h-8 cursor-grab active:cursor-grabbing text-sidebar-foreground/50 hover:text-sidebar-foreground shrink-0"
      >
        <GripVertical className="size-3.5" />
      </span>
      <NavLink
        to={item.to}
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors flex-1",
            isActive && !hidden
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
          )
        }
      >
        <item.icon className="size-4 shrink-0" />
        {!collapsed && <span>{t(item.labelKey)}</span>}
      </NavLink>
      <button
        onClick={onToggleHide}
        className="flex items-center justify-center w-6 h-8 text-sidebar-foreground/50 hover:text-sidebar-foreground shrink-0"
        title={hidden ? t("component.show") : t("component.hide")}
      >
        {hidden ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
      </button>
    </div>
  )
}

export function Sidebar() {
  const { collapsed, toggle, navOrder, hiddenNavs, editMode, toggleEditMode, toggleNavVisibility, setNavOrder } = useSidebar()
  const { logout } = useAuth()
  const t = useT()

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  )

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = navOrder.indexOf(active.id as string)
    const newIndex = navOrder.indexOf(over.id as string)
    const newOrder = [...navOrder]
    newOrder.splice(oldIndex, 1)
    newOrder.splice(newIndex, 0, active.id as string)
    setNavOrder(newOrder)
  }

  const visibleItems = editMode
    ? navOrder.map(p => itemMap.get(p)).filter(Boolean) as NavItem[]
    : navOrder.filter(p => !hiddenNavs.includes(p)).map(p => itemMap.get(p)).filter(Boolean) as NavItem[]

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-sidebar-border bg-sidebar transition-all duration-200",
        collapsed ? "w-14" : "w-56",
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
        {!collapsed && (
          <span className="font-semibold text-sidebar-foreground">CocoCat</span>
        )}
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={toggle}
          className="text-sidebar-foreground"
        >
          {collapsed ? <PanelLeft className="size-4" /> : <PanelLeftClose className="size-4" />}
        </Button>
      </div>

      <nav className="flex-1 space-y-1 p-2 overflow-y-auto">
        {editMode ? (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={navOrder} strategy={verticalListSortingStrategy}>
              {visibleItems.map(item => (
                <SortableNavItem
                  key={item.to}
                  item={item}
                  collapsed={collapsed}
                  hidden={hiddenNavs.includes(item.to)}
                  onToggleHide={() => toggleNavVisibility(item.to)}
                  t={t}
                />
              ))}
            </SortableContext>
          </DndContext>
        ) : (
          visibleItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                )
              }
            >
              <item.icon className="size-4 shrink-0" />
              {!collapsed && <span>{t(item.labelKey)}</span>}
            </NavLink>
          ))
        )}
      </nav>

      <div className="border-t border-sidebar-border p-2 space-y-1">
        {!collapsed && (
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50 transition-colors"
          >
            <LogOut className="size-4 shrink-0" />
            <span>{t("nav.logout")}</span>
          </button>
        )}
        {collapsed && (
          <button
            onClick={logout}
            className="flex w-full items-center justify-center rounded-md px-2 py-2 text-red-500 hover:bg-red-50 transition-colors"
            title={t("nav.logout")}
          >
            <LogOut className="size-4 shrink-0" />
          </button>
        )}
        {/* Edit mode toggle */}
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleEditMode}
          className={cn(
            "w-full flex items-center gap-3 justify-start text-sm font-medium transition-colors",
            editMode
              ? "bg-sidebar-accent text-sidebar-accent-foreground"
              : "text-sidebar-foreground hover:bg-sidebar-accent",
          )}
        >
          <Pencil className="size-4 shrink-0" />
          {!collapsed && <span>{editMode ? t("component.done") : t("component.edit_sidebar")}</span>}
        </Button>
      </div>
    </aside>
  )
}
```

---

### Task 4: Add i18n labels for new strings

**Files:**
- Modify: `web-ui/src/i18n/en.ts`
- Modify: `web-ui/src/i18n/zh.ts`

- [ ] **Add English labels**

Add to `web-ui/src/i18n/en.ts`:
```ts
  "component.edit_sidebar": "Edit Sidebar",
  "component.done": "Done",
  "component.show": "Show",
  "component.hide": "Hide",
```

- [ ] **Add Chinese labels**

Add to `web-ui/src/i18n/zh.ts`:
```ts
  "component.edit_sidebar": "编辑侧边栏",
  "component.done": "完成",
  "component.show": "显示",
  "component.hide": "隐藏",
```
