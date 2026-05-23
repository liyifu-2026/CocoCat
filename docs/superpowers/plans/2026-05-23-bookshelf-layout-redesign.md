# Bookshelf & Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign CocoCat's layout to support chat overlay/collapse, infinite-scroll bookshelf with wiki doc browsing, Raw upload zone, and route-based navigation.

**Architecture:** Replace `useState`-driven panel switching with react-router nested routes. ChatPanel persists across routes, toggling between overlay (420px, covers op display) and collapsed (72px rail). Bookshelf becomes a single-row infinite scroll with snap-to-center 🔻 indicator. KB browsing (directory tree + MD renderer) and Raw upload zone share the BookshelfPage.

**Tech Stack:** React 19, TypeScript, react-router-dom v7, Tailwind CSS 4, shadcn/ui, @tanstack/react-query, @tanstack/react-virtual

---

## File Structure

```
web-ui/src/
├── App.tsx                          → nested routes (modify)
├── components/
│   ├── Layout.tsx                   → use routes, persist ChatPanel (modify)
│   ├── LeftNav.tsx                  → Links instead of onClick (modify)
│   ├── Namecard.tsx                 → animation enh (modify)
│   ├── chat/
│   │   ├── ChatPanel.tsx            → overlay/collapsed dual-mode (modify)
│   │   ├── ChatMessages.tsx         → file card support (modify)
│   │   ├── ChatInput.tsx            → preserves mode indicator (unchanged)
│   │   └── FileCard.tsx             → file attachment card (create)
│   ├── opdisplay/                   → DELETE this directory
│   ├── pages/                       
│   │   ├── ChatPage.tsx             → /app/chat route (create)
│   │   ├── BookshelfPage.tsx        → /app/knowledge/* route (create)
│   │   ├── ScenesPage.tsx           → /app/scenes (create)
│   │   ├── SettingsPage.tsx         → /app/settings (create)
│   │   └── MemoryPage.tsx           → /app/memory (create)
│   ├── bookshelf/
│   │   ├── Bookshelf.tsx            → infinite scroll rewrite (create)
│   │   ├── DocRenderer.tsx          → dir tree + MD body (create)
│   │   ├── RawZone.tsx              → upload staging (create)
│   │   └── SearchPanel.tsx          → 🔻 click quick-select (create)
│   └── FilePreviewOverlay.tsx       → file preview in op area (create)
├── context/
│   └── ChatOverlayContext.tsx       → overlay/collapsed state (create)
```

---

### Task 1: Create ChatOverlayContext

**Files:**
- Create: `web-ui/src/context/ChatOverlayContext.tsx`

- [ ] **Step 1: Write the context provider**

```tsx
import { createContext, useContext, useState, useCallback, type ReactNode } from "react"

type ChatState = "overlay" | "collapsed"

interface ChatOverlayValue {
  chatState: ChatState
  setChatState: (s: ChatState) => void
  toggleChat: () => void
}

const ChatOverlayCtx = createContext<ChatOverlayValue>({
  chatState: "overlay",
  setChatState: () => {},
  toggleChat: () => {},
})

export function ChatOverlayProvider({ children }: { children: ReactNode }) {
  const [chatState, setChatState] = useState<ChatState>("overlay")

  const toggleChat = useCallback(() => {
    setChatState(prev => prev === "overlay" ? "collapsed" : "overlay")
  }, [])

  return (
    <ChatOverlayCtx.Provider value={{ chatState, setChatState, toggleChat }}>
      {children}
    </ChatOverlayCtx.Provider>
  )
}

export function useChatOverlay() {
  return useContext(ChatOverlayCtx)
}
```

- [ ] **Step 2: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: no errors about ChatOverlayContext

### Task 2: Convert App.tsx to Nested Routes

**Files:**
- Modify: `web-ui/src/App.tsx:1-15`
- Create: `web-ui/src/pages/ChatPage.tsx`
- Create: `web-ui/src/pages/BookshelfPage.tsx`
- Create: `web-ui/src/pages/ScenesPage.tsx`
- Create: `web-ui/src/pages/SettingsPage.tsx`
- Create: `web-ui/src/pages/MemoryPage.tsx`

- [ ] **Step 1: Create placeholder page components**

```tsx
// web-ui/src/pages/ChatPage.tsx
import DefaultFunc from "@/components/opdisplay/DefaultFunc"

export default function ChatPage() {
  return <DefaultFunc />
}
```

```tsx
// web-ui/src/pages/BookshelfPage.tsx
export default function BookshelfPage() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden min-w-0">
      <p className="p-8 text-muted-foreground text-xs">Bookshelf — coming in Task 7</p>
    </div>
  )
}
```

```tsx
// web-ui/src/pages/ScenesPage.tsx
import ScenesView from "@/components/opdisplay/ScenesView"

export default function ScenesPage() {
  return <ScenesView />
}
```

```tsx
// web-ui/src/pages/SettingsPage.tsx
import SettingsView from "@/components/opdisplay/SettingsView"

export default function SettingsPage() {
  return <SettingsView />
}
```

```tsx
// web-ui/src/pages/MemoryPage.tsx
import { Brain } from "lucide-react"

export default function MemoryPage() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center h-full animate-view-enter text-center gap-3">
      <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center">
        <Brain className="size-6 text-muted-foreground/40" />
      </div>
      <div>
        <h3 className="text-sm font-medium text-foreground mb-1">Memory Timeline</h3>
        <p className="text-[11px] text-muted-foreground max-w-[240px]">
          Pinned facts and conversation memory will appear here. Use chat to build context.
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite App.tsx with nested routes**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import Layout from "@/components/Layout"
import Login from "@/pages/Login"
import ChatPage from "@/pages/ChatPage"
import BookshelfPage from "@/pages/BookshelfPage"
import ScenesPage from "@/pages/ScenesPage"
import SettingsPage from "@/pages/SettingsPage"
import MemoryPage from "@/pages/MemoryPage"

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route index element={<Navigate to="chat" replace />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="chat/:sessionId" element={<ChatPage />} />
          <Route path="knowledge" element={<BookshelfPage />} />
          <Route path="knowledge/:kbName" element={<BookshelfPage />} />
          <Route path="knowledge/:kbName/:pageType/:pageName" element={<BookshelfPage />} />
          <Route path="scenes" element={<ScenesPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="settings/:tab" element={<SettingsPage />} />
          <Route path="memory" element={<MemoryPage />} />
          <Route path="*" element={<Navigate to="chat" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 3: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds (placeholder pages may have unused imports, that's fine for now)

### Task 3: Refactor Layout — Route-Driven + Persistent ChatPanel

**Files:**
- Modify: `web-ui/src/components/Layout.tsx:1-64`
- Modify: `web-ui/src/main.tsx` (add ChatOverlayProvider)

- [ ] **Step 1: Add ChatOverlayProvider to main.tsx**

Read `web-ui/src/main.tsx` first to find the provider hierarchy. Wrap existing providers with `<ChatOverlayProvider>`.

Expected insertion pattern:
```tsx
import { ChatOverlayProvider } from "@/context/ChatOverlayContext"

// wrap existing providers:
<ChatOverlayProvider>
  {...existingProviders}
</ChatOverlayProvider>
```

- [ ] **Step 2: Rewrite Layout.tsx**

```tsx
import { useEffect, useRef, useCallback } from "react"
import { Outlet, useLocation, useNavigation } from "react-router-dom"
import LeftNav from "./LeftNav"
import ChatPanel from "./chat/ChatPanel"
import { MobileBottomNav } from "./MobileBottomNav"
import { CommandPalette } from "./CommandPalette"
import { useChatOverlay } from "@/context/ChatOverlayContext"
import { cn } from "@/lib/utils"
import { ChevronLeft, MessageSquare } from "lucide-react"
import { useMode } from "@/context/ModeContext"
import { useT } from "@/context/LanguageContext"
import { useState } from "react"

export type QuickSendFn = (message: string) => void

export default function Layout() {
  const location = useLocation()
  const { chatState, setChatState } = useChatOverlay()
  const quickSendRef = useRef<QuickSendFn | null>(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const { currentMode } = useMode()
  const t = useT()

  const isChatRoute = location.pathname.startsWith("/chat")
  const isCollapsedRoute = !isChatRoute

  useEffect(() => {
    if (isCollapsedRoute && chatState === "overlay") {
      setChatState("collapsed")
    } else if (isChatRoute && chatState === "collapsed") {
      setChatState("overlay")
    }
  }, [location.pathname])

  const handleQuickSend = useCallback((message: string) => {
    setTimeout(() => {
      quickSendRef.current?.(message)
    }, 50)
  }, [])

  const registerQuickSend = useCallback((fn: QuickSendFn) => {
    quickSendRef.current = fn
    return () => { quickSendRef.current = null }
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setPaletteOpen(true)
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "[") {
        e.preventDefault()
        setChatState("collapsed")
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "]") {
        e.preventDefault()
        setChatState("overlay")
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [setChatState])

  const isOverlay = chatState === "overlay"

  return (
    <div className="flex h-screen relative">
      <div className="bg-glow-blue" />
      <div className="bg-glow-amber" />

      <LeftNav />

      <div
        className={cn(
          "flex-1 flex flex-col overflow-hidden min-w-0 transition-[margin-right] duration-300 ease-out",
          isOverlay ? "mr-0" : "mr-[72px]"
        )}
      >
        <div className="flex-1 overflow-y-auto no-scrollbar">
          <Outlet />
        </div>
      </div>

      {/* ChatPanel: absolute overlay or fixed-width rail */}
      <div
        className={cn(
          "transition-all duration-300 ease-out shrink-0",
          isOverlay
            ? "w-[420px] absolute right-0 top-0 bottom-0 z-20"
            : "w-[72px] border-l border-sidebar-border bg-sidebar"
        )}
      >
        {isOverlay ? (
          <ChatPanel registerQuickSend={registerQuickSend} onQuickSend={handleQuickSend} />
        ) : (
          <div className="h-full flex flex-col items-center py-4 gap-3">
            <button
              onClick={() => setChatState("overlay")}
              className="w-9 h-9 rounded-xl bg-card border border-border flex items-center justify-center hover:border-primary/30 transition-colors"
              title="Expand chat"
            >
              <ChevronLeft className="size-4 text-muted-foreground" />
            </button>
            <div className={cn(
              "w-9 h-9 rounded-full flex items-center justify-center text-sm",
              currentMode === "kb-admin"
                ? "bg-amber-500/10 text-amber-500"
                : "bg-blue-500/10 text-blue-500"
            )}>
              {currentMode === "kb-admin" ? "📚" : "💬"}
            </div>
            <div className="flex-1" />
            <div className="w-9 h-9 rounded-full bg-card border border-border flex items-center justify-center text-[10px] text-muted-foreground">
              <MessageSquare className="size-4" />
            </div>
          </div>
        )}
      </div>

      <MobileBottomNav />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onNavigate={() => setPaletteOpen(false)}
      />
    </div>
  )
}
```

- [ ] **Step 3: Remove `active` + `onNavigate` from LeftNav**

Read `web-ui/src/components/LeftNav.tsx`. Rewrite as:

```tsx
import { NavLink } from "react-router-dom"
import { MessageSquare, Folder, BookOpen, Brain, Settings } from "lucide-react"
import { cn } from "@/lib/utils"
import { useT } from "@/context/LanguageContext"

const NAV_ITEMS = [
  { path: "/chat", icon: MessageSquare, labelKey: "nav.chat" },
  { path: "/scenes", icon: Folder, labelKey: "nav.scenes" },
  { path: "/knowledge", icon: BookOpen, labelKey: "nav.knowledge" },
  { path: "/memory", icon: Brain, labelKey: "nav.memory" },
  { path: "/settings", icon: Settings, labelKey: "nav.settings" },
] as const

export default function LeftNav() {
  const t = useT()

  return (
    <aside className="w-[76px] bg-sidebar border-r border-sidebar-border flex flex-col items-center shrink-0 py-5 gap-3.5 z-30">
      <NavLink
        to="/chat"
        className="w-11 h-11 bg-card border border-border rounded-2xl flex items-center justify-center cursor-pointer hover:border-primary/30 transition-colors"
      >
        <span className="text-xs font-bold text-primary tracking-widest">CC</span>
      </NavLink>

      <div className="w-8 h-px bg-border/50" />

      {NAV_ITEMS.map(({ path, icon: Icon, labelKey }) => (
        <NavLink
          key={path}
          to={path}
          className={({ isActive }) =>
            cn(
              "w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-200 relative group",
              isActive
                ? "bg-primary text-primary-foreground shadow-lg shadow-primary/25"
                : "text-muted-foreground hover:bg-card hover:text-foreground"
            )
          }
        >
          {({ isActive }) => (
            <>
              <Icon className="size-5" />
              <span className="absolute left-14 bg-popover text-muted-foreground text-[9px] px-2 py-1 rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 shadow-lg border border-border">
                {t(labelKey)}
              </span>
            </>
          )}
        </NavLink>
      ))}

      <div className="mt-auto w-9 h-9 rounded-full bg-muted border-2 border-emerald-500/30" />
    </aside>
  )
}
```

- [ ] **Step 4: Remove `active` + `onNavigate` from MobileBottomNav**

Read `web-ui/src/components/MobileBottomNav.tsx`. Convert to use `<NavLink>` instead of `active` + `onNavigate` props.

- [ ] **Step 5: Remove `active` + `onNavigate` from CommandPalette**

Read `web-ui/src/components/CommandPalette.tsx`. Replace `onNavigate` with `useNavigate()` from react-router.

- [ ] **Step 6: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds

### Task 4: Update ChatPanel for Collapsed Rail + Quick Send Removal

**Files:**
- Modify: `web-ui/src/components/chat/ChatPanel.tsx:1-166`

- [ ] **Step 1: Add `onQuickSend` prop, remove Layout dependency**

```tsx
// In web-ui/src/components/chat/ChatPanel.tsx, modify interface:
interface ChatPanelProps {
  registerQuickSend?: (fn: QuickSendFn) => () => void
  onQuickSend?: QuickSendFn
}

// Move QuickSendFn type definition into ChatPanel itself:
type QuickSendFn = (message: string) => void
```

Change import: remove `import type { QuickSendFn } from "../Layout"`, add local `type QuickSendFn = (message: string) => void`.

- [ ] **Step 2: Add collapsed rail rendering**

Add a new export or prop to ChatPanel. When `collapsed` prop is true, render only the rail content. Keep it simple — the rail is already rendered in Layout for now, so this is a forward-compatibility step.

Actually, looking at the design, the collapsed rail is rendered in Layout.tsx directly. ChatPanel itself only renders in overlay mode. So the Layout change from Task 3 already handles this. No ChatPanel changes needed for collapsed mode.

- [ ] **Step 3: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds

### Task 5: Remove Old OpDisplay Components

**Files:**
- Delete: `web-ui/src/components/OpDisplay.tsx`
- Delete: `web-ui/src/components/opdisplay/KbAdminFunc.tsx`
- Delete: `web-ui/src/components/opdisplay/KnowledgeView.tsx`

- [ ] **Step 1: Update ChatPage.tsx to include Namecard**

Rewrite `web-ui/src/pages/ChatPage.tsx`:

```tsx
import Namecard from "@/components/Namecard"
import VizEngine from "@/components/viz/VizEngine"
import DefaultFunc from "@/components/opdisplay/DefaultFunc"

export default function ChatPage() {
  return (
    <>
      <Namecard />
      <VizEngine />
      <DefaultFunc />
    </>
  )
}
```

- [ ] **Step 2: Update other pages to include Namecard**

Rewrite `web-ui/src/pages/ScenesPage.tsx`:
```tsx
import Namecard from "@/components/Namecard"
import VizEngine from "@/components/viz/VizEngine"
import ScenesView from "@/components/opdisplay/ScenesView"

export default function ScenesPage() {
  return (
    <>
      <Namecard />
      <VizEngine />
      <ScenesView />
    </>
  )
}
```

Rewrite `web-ui/src/pages/SettingsPage.tsx`:
```tsx
import Namecard from "@/components/Namecard"
import VizEngine from "@/components/viz/VizEngine"
import SettingsView from "@/components/opdisplay/SettingsView"

export default function SettingsPage() {
  return (
    <>
      <Namecard />
      <VizEngine />
      <SettingsView />
    </>
  )
}
```

Rewrite `web-ui/src/pages/MemoryPage.tsx`:
```tsx
import Namecard from "@/components/Namecard"
import VizEngine from "@/components/viz/VizEngine"
import { Brain } from "lucide-react"

export default function MemoryPage() {
  return (
    <>
      <Namecard />
      <VizEngine />
      <div className="flex-1 flex flex-col items-center justify-center text-center gap-3">
        <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center">
          <Brain className="size-6 text-muted-foreground/40" />
        </div>
        <div>
          <h3 className="text-sm font-medium text-foreground mb-1">Memory Timeline</h3>
          <p className="text-[11px] text-muted-foreground max-w-[240px]">
            Pinned facts and conversation memory will appear here. Use chat to build context.
          </p>
        </div>
      </div>
    </>
  )
}
```

- [ ] **Step 3: Delete old files**

```bash
rm web-ui/src/components/OpDisplay.tsx
rm web-ui/src/components/opdisplay/KbAdminFunc.tsx
rm web-ui/src/components/opdisplay/KnowledgeView.tsx
```

- [ ] **Step 4: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds, no imports to OpDisplay/KbAdminFunc/KnowledgeView remain

### Task 6: Rewrite Bookshelf — Infinite Scroll with Snap

**Files:**
- Delete: `web-ui/src/components/opdisplay/Bookshelf.tsx`
- Create: `web-ui/src/components/bookshelf/Bookshelf.tsx`
- Create: `web-ui/src/components/bookshelf/SearchPanel.tsx`

- [ ] **Step 1: Write Bookshelf component**

```tsx
import { useRef, useCallback, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import SearchPanel from "./SearchPanel"
import { ChevronDown } from "lucide-react"

const COVER_COLORS: { bg: string; accent: string; pattern: string }[] = [
  { bg: "bg-gradient-to-br from-blue-700 to-blue-900", accent: "#93c5fd", pattern: "circle" },
  { bg: "bg-gradient-to-br from-indigo-700 to-indigo-900", accent: "#a5b4fc", pattern: "diamond" },
  { bg: "bg-gradient-to-br from-cyan-700 to-cyan-900", accent: "#67e8f9", pattern: "wave" },
  { bg: "bg-gradient-to-br from-amber-700 to-amber-900", accent: "#fcd34d", pattern: "cross" },
  { bg: "bg-gradient-to-br from-rose-700 to-rose-900", accent: "#fda4af", pattern: "lines" },
  { bg: "bg-gradient-to-br from-emerald-700 to-emerald-900", accent: "#6ee7b7", pattern: "circle" },
  { bg: "bg-gradient-to-br from-violet-700 to-violet-900", accent: "#c4b5fd", pattern: "diamond" },
  { bg: "bg-gradient-to-br from-sky-700 to-sky-900", accent: "#bae6fd", pattern: "wave" },
]

interface KbInfo { id: string; purpose?: string }

const BOOK_WIDTH = 80

interface Props {
  selectedKb: string | null
  onSelect: (kbName: string) => void
}

export default function Bookshelf({ selectedKb, onSelect }: Props) {
  const shelfRef = useRef<HTMLDivElement>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const navigate = useNavigate()
  const t = useT()

  const { data } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetch("/api/knowledge").then(r => r.json()),
  })

  const kbs: KbInfo[] = (data as any)?.kbs ?? []
  const totalWidth = kbs.length * BOOK_WIDTH

  useEffect(() => {
    if (!selectedKb || !shelfRef.current) return
    const idx = kbs.findIndex(k => k.id === selectedKb)
    if (idx < 0) return
    shelfRef.current.scrollLeft = idx * BOOK_WIDTH - shelfRef.current.clientWidth / 2 + BOOK_WIDTH / 2
  }, [selectedKb, kbs])

  const handleScroll = useCallback(() => {
    if (!shelfRef.current) return
    const el = shelfRef.current
    const center = el.scrollLeft + el.clientWidth / 2
    const idx = Math.round(center / BOOK_WIDTH)
    const clampedIdx = Math.max(0, Math.min(idx, kbs.length - 1))
    if (kbs[clampedIdx] && kbs[clampedIdx].id !== selectedKb) {
      onSelect(kbs[clampedIdx].id)
    }
  }, [kbs, selectedKb, onSelect])

  const handleBookClick = (kbName: string) => {
    onSelect(kbName)
    navigate(`/knowledge/${kbName}`)
  }

  const handleSearchSelect = (kbName: string) => {
    onSelect(kbName)
    navigate(`/knowledge/${kbName}`)
    setSearchOpen(false)
  }

  if (kbs.length === 0) {
    return (
      <div className="h-[120px] flex items-center justify-center">
        <p className="text-[11px] text-muted-foreground/40">{t("knowledge.no_kbs")}</p>
      </div>
    )
  }

  return (
    <div className="relative h-[120px] select-none">
      {/* 🔻 indicator — fixed center */}
      <button
        onClick={() => setSearchOpen(true)}
        className="absolute top-0 left-1/2 -translate-x-1/2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-card border border-border shadow-md hover:border-primary/40 transition-colors cursor-pointer"
        title="Search knowledge bases"
      >
        <ChevronDown className="size-4 text-primary" />
      </button>

      {/* Bookshelf scroll container */}
      <div
        ref={shelfRef}
        className="overflow-x-auto no-scrollbar snap-x snap-mandatory pt-10 pb-2"
        onScroll={handleScroll}
        style={{ scrollSnapType: "x mandatory" }}
      >
        <div className="flex" style={{ width: totalWidth + 200 }}>
          {/* Left spacer for centering */}
          <div className="shrink-0" style={{ width: "calc(50vw - 38px - 36px - 40px)" }} />

          {kbs.map((kb, i) => {
            const color = COVER_COLORS[i % COVER_COLORS.length]!
            const isSelected = kb.id === selectedKb
            return (
              <div
                key={kb.id}
                className={cn(
                  "shrink-0 snap-center cursor-pointer transition-all duration-200",
                  isSelected ? "scale-110 z-10" : "hover:scale-105"
                )}
                style={{ width: BOOK_WIDTH }}
                onClick={() => handleBookClick(kb.id)}
              >
                <div
                  className={cn(
                    "h-20 rounded-lg relative overflow-hidden shadow-md flex flex-col justify-end p-1.5",
                    color.bg,
                    isSelected && "ring-2 ring-primary ring-offset-2 ring-offset-background"
                  )}
                >
                  <h5 className="text-[8px] font-bold text-white/90 truncate">{kb.id}</h5>
                </div>
              </div>
            )
          })}

          {/* "New KB" placeholder */}
          <div className="shrink-0 snap-center cursor-pointer" style={{ width: BOOK_WIDTH }}
            onClick={() => navigate("/settings/kb")}
          >
            <div className="h-20 rounded-lg border-2 border-dashed border-border flex items-center justify-center hover:border-primary/30 transition-colors">
              <span className="text-muted-foreground/40 text-lg">+</span>
            </div>
          </div>

          {/* Right spacer */}
          <div className="shrink-0" style={{ width: "calc(50vw - 38px - 36px - 40px)" }} />
        </div>
      </div>

      {searchOpen && (
        <SearchPanel
          kbs={kbs}
          onSelect={handleSearchSelect}
          onClose={() => setSearchOpen(false)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Write SearchPanel component**

```tsx
import { useState, useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import { Search, X } from "lucide-react"

interface KbInfo { id: string; purpose?: string }

interface Props {
  kbs: KbInfo[]
  onSelect: (kbName: string) => void
  onClose: () => void
}

export default function SearchPanel({ kbs, onSelect, onClose }: Props) {
  const [query, setQuery] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [onClose])

  const filtered = query
    ? kbs.filter(k => k.id.toLowerCase().includes(query.toLowerCase()))
    : kbs

  return (
    <div className="absolute top-12 left-1/2 -translate-x-1/2 z-50 w-64 bg-popover border border-border rounded-xl shadow-xl p-3 space-y-2 animate-scaleIn">
      <div className="flex items-center gap-2 bg-input border border-border rounded-lg px-3 py-1.5">
        <Search className="size-3.5 text-muted-foreground" />
        <input
          ref={inputRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search KB..."
          className="flex-1 bg-transparent border-none outline-none text-xs text-foreground placeholder:text-muted-foreground/40"
        />
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="size-3.5" />
        </button>
      </div>
      <div className="max-h-48 overflow-y-auto space-y-0.5">
        {filtered.map(kb => (
          <button
            key={kb.id}
            onClick={() => onSelect(kb.id)}
            className="w-full text-left px-3 py-2 rounded-lg text-xs hover:bg-muted transition-colors flex flex-col"
          >
            <span className="font-medium text-foreground">{kb.id}</span>
            {kb.purpose && <span className="text-[9px] text-muted-foreground truncate">{kb.purpose}</span>}
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="text-center text-[10px] text-muted-foreground py-4">No matches</p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Add CSS animation for scaleIn**

Read `web-ui/src/index.css`. Append:

```css
@keyframes scaleIn {
  from { opacity: 0; transform: translate(-50%, -4px) scale(0.95); }
  to { opacity: 1; transform: translate(-50%, 0) scale(1); }
}
.animate-scaleIn {
  animation: scaleIn 0.15s ease-out;
}
```

- [ ] **Step 4: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds

### Task 7: Create DocRenderer (Directory Tree + MD Body)

**Files:**
- Create: `web-ui/src/components/bookshelf/DocRenderer.tsx`

- [ ] **Step 1: Write DocRenderer component**

```tsx
import { useState, useEffect, useCallback } from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { BookOpen, Search, ChevronRight, ChevronDown, FileText, X } from "lucide-react"
import MermaidBlock from "@/components/MermaidBlock"

interface WikiItem {
  name: string
  url?: string
  description?: string
}

interface WikiData {
  entities?: WikiItem[]
  concepts?: WikiItem[]
  pages?: WikiItem[]
}

interface Props {
  kbName: string | null
}

export default function DocRenderer({ kbName }: Props) {
  const navigate = useNavigate()
  const { pageType, pageName } = useParams()
  const t = useT()
  const [searchQuery, setSearchQuery] = useState("")

  const { data: wikiData, isLoading: wikiLoading } = useQuery({
    queryKey: ["wiki", kbName],
    queryFn: () => fetch(`/api/knowledge/${kbName}/wiki`).then(r => r.json()),
    enabled: !!kbName,
  })

  const wiki = (wikiData as WikiData) || {}
  const entities = (wiki.entities || []) as WikiItem[]
  const concepts = (wiki.concepts || []) as WikiItem[]
  const pages = (wiki.pages || []) as WikiItem[]

  const { data: pageData, isLoading: pageLoading } = useQuery({
    queryKey: ["wiki-page", kbName, pageType, pageName],
    queryFn: () => fetch(`/api/knowledge/${kbName}/wiki/${pageType}/${pageName}`).then(r => r.json()),
    enabled: !!kbName && !!pageType && !!pageName,
  })

  const filterBySearch = (items: WikiItem[]) => {
    if (!searchQuery) return items
    const q = searchQuery.toLowerCase()
    return items.filter(item =>
      item.name.toLowerCase().includes(q) ||
      (item.description && item.description.toLowerCase().includes(q))
    )
  }

  const allFiltered = {
    entities: filterBySearch(entities),
    concepts: filterBySearch(concepts),
    pages: filterBySearch(pages),
  }

  const handleWikiClick = (item: WikiItem, section: string) => {
    navigate(`/knowledge/${kbName}/${section}/${item.name}`)
  }

  if (!kbName) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground/40">
        <div className="text-center">
          <BookOpen className="size-8 mx-auto mb-2 opacity-30" />
          <p className="text-xs">Select a knowledge base to browse</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Directory tree */}
      <div className="w-[220px] border-r border-border overflow-y-auto no-scrollbar p-3 space-y-3 shrink-0">
        <div className="flex items-center gap-2 bg-input border border-border rounded-lg px-2.5 py-1.5">
          <Search className="size-3 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder={t("knowledge.search_wiki")}
            className="flex-1 bg-transparent border-none outline-none text-[10px] text-foreground placeholder:text-muted-foreground/40"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery("")} className="text-muted-foreground">
              <X className="size-3" />
            </button>
          )}
        </div>

        <WikiSection title="Entities" items={allFiltered.entities} activePage={`${pageType}/${pageName}`} section="entities" onSelect={handleWikiClick} />
        <WikiSection title="Concepts" items={allFiltered.concepts} activePage={`${pageType}/${pageName}`} section="concepts" onSelect={handleWikiClick} />
        <WikiSection title="Pages" items={allFiltered.pages} activePage={`${pageType}/${pageName}`} section="pages" onSelect={handleWikiClick} />
      </div>

      {/* MD content */}
      <div className="flex-1 overflow-y-auto p-5">
        {pageLoading ? (
          <div className="space-y-3 animate-pulse">
            <div className="h-6 w-1/3 bg-muted rounded" />
            <div className="h-4 w-full bg-muted rounded" />
            <div className="h-4 w-3/4 bg-muted rounded" />
          </div>
        ) : pageData ? (
          <div className="markdown-content text-sm">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                pre: ({ children }) => <>{children}</>,
                code: ({ className, children, ...props }) => {
                  const match = /language-(\w+)/.exec(className || "")
                  const isMermaid = match && match[1] === "mermaid"
                  if (isMermaid) return <MermaidBlock chart={String(children)} />
                  const isInline = !match && !String(children).includes("\n")
                  if (isInline) return <code className={className} {...props}>{children}</code>
                  return (
                    <pre className="bg-muted rounded-lg p-4 overflow-x-auto text-xs">
                      <code className={className} {...props}>{children}</code>
                    </pre>
                  )
                },
              }}
            >
              {typeof (pageData as any)?.content === "string"
                ? (pageData as any).content
                : (pageData as any)?.markdown || JSON.stringify(pageData)}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground/40">
            <div className="text-center">
              <FileText className="size-8 mx-auto mb-2 opacity-30" />
              <p className="text-xs">{t("knowledge.select_page")}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function WikiSection({
  title, items, activePage, section, onSelect,
}: {
  title: string
  items: WikiItem[]
  activePage: string
  section: string
  onSelect: (item: WikiItem, section: string) => void
}) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1 hover:text-foreground transition-colors"
      >
        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        {title} ({items.length})
      </button>
      {expanded && (
        <div className="space-y-0.5 pl-1">
          {items.map(item => {
            const isActive = `${section}/${item.name}` === activePage
            return (
              <button
                key={item.name}
                onClick={() => onSelect(item, section)}
                className={cn(
                  "w-full text-left px-2.5 py-1.5 rounded-md text-[10px] transition-colors truncate",
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                {item.name}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds (MermaidBlock import may need adjustment — check actual path)

- [ ] **Step 3: Check MermaidBlock path**

Read `web-ui/src/components/MermaidBlock.tsx`. Verify the export surface. If it exports `{ MermaidBlock }` as named export, adjust import accordingly.

### Task 8: Create RawZone Component

**Files:**
- Create: `web-ui/src/components/bookshelf/RawZone.tsx`

- [ ] **Step 1: Write RawZone component**

```tsx
import { useState, useRef, useCallback } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import { ChevronDown, ChevronUp, Upload, FileText, X, Loader2, Send } from "lucide-react"

interface RawFile {
  name: string
  size: number
}

export default function RawZone() {
  const [expanded, setExpanded] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const t = useT()

  const { data: rawFiles } = useQuery({
    queryKey: ["raw-files"],
    queryFn: () => fetch("/api/knowledge/.raw").then(r => r.json()),
    enabled: expanded,
  })

  const files: RawFile[] = (rawFiles as any)?.files ?? []

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  }

  const handleUpload = useCallback(async (fileList: FileList | null) => {
    if (!fileList?.length) return
    setUploading(true)
    for (const file of Array.from(fileList)) {
      const formData = new FormData()
      formData.append("file", file)
      await fetch("/api/knowledge/.raw/upload", { method: "POST", body: formData })
    }
    queryClient.invalidateQueries({ queryKey: ["raw-files"] })
    setUploading(false)
  }, [queryClient])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    handleUpload(e.dataTransfer.files)
  }, [handleUpload])

  const handleDelete = async (filename: string) => {
    await fetch(`/api/knowledge/.raw/${encodeURIComponent(filename)}`, { method: "DELETE" })
    queryClient.invalidateQueries({ queryKey: ["raw-files"] })
  }

  return (
    <div className="border-t border-border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Upload className="size-3.5 text-muted-foreground" />
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            Raw Staging
          </span>
          {files.length > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">{files.length}</span>
          )}
        </div>
        {expanded ? <ChevronDown className="size-3.5 text-muted-foreground" /> : <ChevronUp className="size-3.5 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-2">
          <div
            className="border border-dashed border-border rounded-xl p-3 text-center cursor-pointer hover:border-primary/30 transition-colors"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
          >
            {uploading ? (
              <div className="flex items-center justify-center gap-2 text-[10px] text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                Uploading...
              </div>
            ) : (
              <>
                <FileText className="size-4 text-muted-foreground/40 mx-auto mb-1" />
                <p className="text-[10px] text-muted-foreground/50">Drop files or click to upload</p>
              </>
            )}
          </div>

          {files.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {files.map(f => (
                <div key={f.name} className="flex items-center gap-2 bg-card border border-border rounded-lg px-2.5 py-1.5 text-[10px]">
                  <FileText className="size-3 text-muted-foreground" />
                  <span className="max-w-[120px] truncate">{f.name}</span>
                  <span className="text-muted-foreground/50">{formatSize(f.size)}</span>
                  <button onClick={() => handleDelete(f.name)} className="text-muted-foreground hover:text-red-400">
                    <X className="size-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {files.length > 0 && (
            <button
              onClick={() => {
                // Dispatch a custom event that BookshelfPage listens to
                window.dispatchEvent(new CustomEvent("raw-organize", { detail: { files } }))
              }}
              className="w-full flex items-center justify-center gap-1.5 bg-primary/10 text-primary text-[10px] font-medium py-2 rounded-lg hover:bg-primary/20 transition-colors"
            >
              <Send className="size-3" />
              Ask agent to organize
            </button>
          )}

          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={e => { handleUpload(e.target.files); e.target.value = "" }}
          />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds (API endpoints not yet implemented — 404s at runtime OK for now)

### Task 9: Build BookshelfPage with All Sub-components

**Files:**
- Modify: `web-ui/src/pages/BookshelfPage.tsx`

- [ ] **Step 1: Rewrite BookshelfPage**

```tsx
import { useParams } from "react-router-dom"
import { useCallback } from "react"
import Namecard from "@/components/Namecard"
import VizEngine from "@/components/viz/VizEngine"
import Bookshelf from "@/components/bookshelf/Bookshelf"
import DocRenderer from "@/components/bookshelf/DocRenderer"
import RawZone from "@/components/bookshelf/RawZone"

export default function BookshelfPage() {
  const { kbName } = useParams()

  const handleSelect = useCallback((name: string) => {
    // Bookshelf handles navigation internally
  }, [])

  return (
    <>
      <Namecard />
      <VizEngine />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <DocRenderer kbName={kbName || null} />
        <Bookshelf selectedKb={kbName || null} onSelect={handleSelect} />
        <RawZone />
      </div>
    </>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds

### Task 10: Namecard Animation Enhancement

**Files:**
- Modify: `web-ui/src/components/Namecard.tsx:1-103`

- [ ] **Step 1: Add cross-fade gradient layers and icon animation**

```tsx
import { useState } from "react"
import { useMode } from "@/context/ModeContext"
import { useT } from "@/context/LanguageContext"
import { cn } from "@/lib/utils"
import { ChevronDown } from "lucide-react"

const MODE_STYLES = {
  default: {
    icon: "💬",
    titleKey: "chat.empty_title",
    subtitleKey: "mode.default",
    statusKey: "mode.default_status",
    bannerGradient: "from-blue-600 via-blue-500 to-indigo-500",
    avatarBg: "bg-blue-100 border-blue-300",
  },
  "kb-admin": {
    icon: "📚",
    titleKey: "mode.kb-admin",
    subtitleKey: "mode.kb_admin_subtitle",
    statusKey: "mode.kb_admin_status",
    bannerGradient: "from-amber-600 via-amber-500 to-orange-500",
    avatarBg: "bg-amber-100 border-amber-300",
  },
} as const

type ModeKey = keyof typeof MODE_STYLES

export default function Namecard() {
  const { currentMode, modes, setMode } = useMode()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [animating, setAnimating] = useState(false)
  const t = useT()

  const style = MODE_STYLES[(
    currentMode in MODE_STYLES ? currentMode : "default"
  ) as ModeKey]
  const prevStyle = currentMode === "kb-admin"
    ? MODE_STYLES.default
    : MODE_STYLES["kb-admin"]

  const handleModeSwitch = (mode: string) => {
    setAnimating(true)
    setMode(mode)
    setDropdownOpen(false)
    setTimeout(() => setAnimating(false), 400)
  }

  return (
    <div className="flex-shrink-0 animate-view-enter">
      {/* Banner with cross-fade gradient */}
      <div className="relative overflow-hidden h-40">
        {/* Current gradient (fading in when mode changes) */}
        <div
          className={cn(
            "absolute inset-0 bg-gradient-to-br transition-opacity duration-400 ease-out",
            style.bannerGradient,
            animating ? "opacity-100" : "opacity-100"
          )}
        />

        {/* Radial glow accent */}
        <div className="absolute top-0 right-0 w-48 h-48 bg-white/8 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/4 w-32 h-32 bg-white/5 rounded-full blur-2xl pointer-events-none" />

        {/* Wave SVG */}
        <svg className="absolute bottom-0 left-0 w-full h-20 pointer-events-none" viewBox="0 0 1200 120" preserveAspectRatio="none">
          <path d="M0,60 C200,110 400,10 600,60 C800,110 1000,10 1200,60 L1200,120 L0,120 Z" fill="var(--background)" opacity="0.25" />
          <path d="M0,80 C300,30 500,110 700,70 C900,30 1100,100 1200,70 L1200,120 L0,120 Z" fill="var(--background)" opacity="0.12" />
        </svg>

        <div className="relative z-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4 px-5 h-full pb-4">
          <div className="flex items-end gap-4 self-end">
            <div
              className={cn(
                "w-20 h-20 rounded-full flex items-center justify-center text-3xl border-[3px] shadow-xl shrink-0 transition-all duration-300",
                style.avatarBg,
                animating && "animate-icon-flip"
              )}
            >
              {style.icon}
            </div>
            <div className="pb-1 space-y-0.5">
              <div className="flex items-center gap-2">
                <h1
                  className={cn(
                    "text-xl font-bold text-white tracking-wide transition-all duration-300",
                    animating && "animate-title-slide"
                  )}
                  key={currentMode}
                >
                  {t(style.titleKey)}
                </h1>
                <div className="relative">
                  <button
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    className="text-[10px] px-2.5 py-0.5 rounded-full font-medium cursor-pointer transition-colors flex items-center gap-1 bg-white/15 text-white"
                    title={t(style.subtitleKey)}
                  >
                    {currentMode} <ChevronDown className="size-3" />
                  </button>
                  {dropdownOpen && (
                    <div className="absolute top-full left-0 mt-1 bg-popover border border-border rounded-lg py-1 shadow-lg z-20 min-w-[130px]">
                      {modes.map(m => (
                        <button
                          key={m.id}
                          onClick={() => handleModeSwitch(m.id)}
                          className={cn(
                            "w-full text-left px-3 py-1.5 text-[10px] rounded-md transition-colors",
                            m.id === currentMode ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-card"
                          )}
                        >
                          {m.name}
                        </button>
                      ))}
                    </div>
                  )}
                  {dropdownOpen && <div className="fixed inset-0 z-10" onClick={() => setDropdownOpen(false)} />}
                </div>
              </div>
              <p
                className="text-xs text-white/70 transition-all duration-300"
                key={`sub-${currentMode}`}
              >
                {t(style.subtitleKey)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Intro Quote */}
      <div className="px-5 py-4">
        <p className={cn(
          "text-[11px] italic text-muted-foreground border-l-2 pl-3 transition-colors duration-300",
          currentMode === "kb-admin" ? "border-amber-400/40" : "border-primary/40"
        )}>
          {t(style.statusKey)}
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add animation keyframes to index.css**

Read `web-ui/src/index.css`. Append at end:

```css
@keyframes iconFlip {
  0% { transform: rotateY(0deg) scale(1); }
  50% { transform: rotateY(90deg) scale(0.8); }
  100% { transform: rotateY(0deg) scale(1); }
}
.animate-icon-flip {
  animation: iconFlip 0.35s ease-out;
}
@keyframes titleSlide {
  0% { opacity: 0; transform: translateY(8px); }
  100% { opacity: 1; transform: translateY(0); }
}
.animate-title-slide {
  animation: titleSlide 0.25s ease-out both;
}
```

- [ ] **Step 3: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds

### Task 11: File Card in Chat + File Preview Overlay

**Files:**
- Create: `web-ui/src/components/chat/FileCard.tsx`
- Create: `web-ui/src/components/FilePreviewOverlay.tsx`
- Modify: `web-ui/src/components/chat/ChatMessages.tsx` (add FileCard rendering support)

- [ ] **Step 1: Write FileCard component**

```tsx
import { FileText, FileImage, FileCode, File } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ReactNode } from "react"

interface Props {
  filename: string
  fileType: string
  fileUrl?: string
  onClick?: () => void
}

const typeIcons: Record<string, ReactNode> = {
  md: <FileText className="size-4 text-blue-400" />,
  pdf: <FileText className="size-4 text-red-400" />,
  png: <FileImage className="size-4 text-green-400" />,
  jpg: <FileImage className="size-4 text-green-400" />,
  jpeg: <FileImage className="size-4 text-green-400" />,
  svg: <FileImage className="size-4 text-green-400" />,
  gif: <FileImage className="size-4 text-green-400" />,
  py: <FileCode className="size-4 text-yellow-400" />,
  ts: <FileCode className="size-4 text-blue-400" />,
  tsx: <FileCode className="size-4 text-blue-400" />,
  js: <FileCode className="size-4 text-yellow-400" />,
  jsx: <FileCode className="size-4 text-blue-400" />,
  json: <FileCode className="size-4 text-orange-400" />,
  yaml: <FileCode className="size-4 text-purple-400" />,
  yml: <FileCode className="size-4 text-purple-400" />,
  css: <FileCode className="size-4 text-pink-400" />,
}

export default function FileCard({ filename, fileType, onClick }: Props) {
  const ext = filename.split(".").pop()?.toLowerCase() || ""
  const icon = typeIcons[ext] || <File className="size-4 text-muted-foreground" />

  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 bg-card border border-border rounded-xl px-3 py-2.5 cursor-pointer hover:border-primary/30 hover:shadow-sm transition-all group",
        "max-w-[260px]"
      )}
    >
      <div className="shrink-0">{icon}</div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-medium text-foreground truncate">{filename}</p>
        <p className="text-[8px] text-muted-foreground">{fileType}</p>
      </div>
      <span className="text-[8px] px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
        Preview
      </span>
    </div>
  )
}
```

- [ ] **Step 2: Write FilePreviewOverlay**

```tsx
import { X } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { ReactNode } from "react"

interface Props {
  filename: string
  content: string
  fileType: string
  onClose: () => void
}

export default function FilePreviewOverlay({ filename, content, fileType, onClose }: Props) {
  const ext = fileType.toLowerCase()

  const renderContent = (): ReactNode => {
    if (["png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext)) {
      return (
        <div className="flex items-center justify-center h-full">
          <img src={content} alt={filename} className="max-w-full max-h-full object-contain rounded-lg" />
        </div>
      )
    }

    if (ext === "pdf") {
      return (
        <iframe src={content} className="w-full h-full rounded-lg" title={filename} />
      )
    }

    if (["py", "ts", "tsx", "js", "jsx", "json", "yaml", "yml", "css", "html", "sh", "bash"].includes(ext)) {
      return (
        <pre className="bg-muted rounded-lg p-4 overflow-auto text-xs font-mono h-full">
          <code>{content}</code>
        </pre>
      )
    }

    // Default: render as markdown
    return (
      <div className="markdown-content text-sm overflow-auto h-full">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    )
  }

  return (
    <div className="absolute inset-0 z-40 bg-background flex flex-col animate-view-enter">
      <div className="flex items-center gap-3 px-5 py-3 border-b border-border shrink-0">
        <button onClick={onClose} className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground transition-colors">
          <X className="size-3.5" />
          Back to chat
        </button>
        <span className="text-[11px] font-medium text-foreground truncate">{filename}</span>
        <span className="text-[9px] text-muted-foreground/50 ml-auto">{fileType}</span>
      </div>
      <div className="flex-1 overflow-hidden p-4">
        {renderContent()}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Wire FileCard into ChatMessages**

In ChatMessages.tsx, find the message bubble section (around line 180-200). After the message bubble, before the timestamp, add a check for file attachments in message content. The FileCard detection can be done by checking if the message content contains a file reference pattern. For now, add a comment placeholder.

Actually: We need to define how files appear in messages. The simplest approach: when the backend includes a `files` array in the response, the frontend renders FileCards. We'll need to update the `Message` type.

Read `web-ui/src/types/chat.ts`. Check the Message type.

If it has a `files` field, use it. If not, add it:

```typescript
// In web-ui/src/types/chat.ts, add to Message:
files?: { name: string; type: string; url?: string }[]
```

Then in ChatMessages, render FileCard items:
```tsx
{m.role === "assistant" && m.files && m.files.length > 0 && (
  <div className="flex flex-wrap gap-2 mb-1">
    {m.files.map((f, i) => (
      <FileCard
        key={i}
        filename={f.name}
        fileType={f.type}
        onClick={() => { /* dispatch file preview */ }}
      />
    ))}
  </div>
)}
```

For now, we skip the file preview dispatch wiring (requires ChatOverlayContext integration which will be finalized in Task 12). We add it as a stub.

- [ ] **Step 4: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds

### Task 12: Wire Up File Preview Dispatch + ChatOverlayContext Integration

**Files:**
- Modify: `web-ui/src/components/chat/ChatMessages.tsx`
- Modify: `web-ui/src/context/ChatOverlayContext.tsx`
- Modify: `web-ui/src/types/chat.ts`

- [ ] **Step 1: Update ChatOverlayContext to support file preview state**

```tsx
// Add to ChatOverlayContext:

interface FilePreview {
  filename: string
  content: string
  type: string
}

interface ChatOverlayValue {
  chatState: ChatState
  setChatState: (s: ChatState) => void
  toggleChat: () => void
  filePreview: FilePreview | null
  openFilePreview: (fp: FilePreview) => void
  closeFilePreview: () => void
}

// Provider:
const [filePreview, setFilePreview] = useState<FilePreview | null>(null)

const openFilePreview = useCallback((fp: FilePreview) => {
  setFilePreview(fp)
  setChatState("collapsed")
}, [])

const closeFilePreview = useCallback(() => {
  setFilePreview(null)
}, [])

// Add to value: filePreview, openFilePreview, closeFilePreview
```

- [ ] **Step 2: Wire file click in ChatMessages**

In `ChatMessages.tsx`, import `useChatOverlay` and `FileCard`:

```tsx
import { useChatOverlay } from "@/context/ChatOverlayContext"
import FileCard from "./FileCard"

// Inside ChatMessages:
const { openFilePreview } = useChatOverlay()

// In message rendering, after the message bubble:
{m.role === "assistant" && m.files && m.files.length > 0 && (
  <div className="flex flex-wrap gap-2 mt-1.5">
    {m.files.map((f, i) => (
      <FileCard
        key={i}
        filename={f.name}
        fileType={f.type}
        onClick={() => openFilePreview({ filename: f.name, content: f.url || "", type: f.type })}
      />
    ))}
  </div>
)}
```

- [ ] **Step 3: Render FilePreviewOverlay in Layout**

In `Layout.tsx`, import and conditionally render:

```tsx
import FilePreviewOverlay from "@/components/FilePreviewOverlay"
import { useChatOverlay } from "@/context/ChatOverlayContext"

// Inside Layout:
const { filePreview, closeFilePreview } = useChatOverlay()

// In the operation area div, after <Outlet />:
{filePreview && (
  <FilePreviewOverlay
    filename={filePreview.filename}
    content={filePreview.content}
    fileType={filePreview.type}
    onClose={closeFilePreview}
  />
)}
```

- [ ] **Step 4: Add Message.files type**

Read `web-ui/src/types/chat.ts`. Add:
```typescript
files?: { name: string; type: string; url?: string }[]
```
to the Message interface.

- [ ] **Step 5: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds

### Task 13: Add Backend Raw Endpoints

**Files:**
- Modify: `cococat/routes/knowledge.py`

- [ ] **Step 1: Add raw endpoints to knowledge.py**

Read the current knowledge.py to find the router. Add these endpoints:

```python
import shutil
from pathlib import Path

RAW_DIR_NAME = ".raw"

def _raw_dir(context) -> Path:
    return Path(context.config_store.knowledge_dir) / RAW_DIR_NAME

@router.get("/.raw")
async def list_raw_files(context: AppContext = Depends(get_context)):
    raw = _raw_dir(context)
    if not raw.exists():
        return {"files": []}
    files = []
    for f in raw.iterdir():
        if f.is_file():
            files.append({"name": f.name, "size": f.stat().st_size})
    return {"files": files}

@router.post("/.raw/upload")
async def upload_raw(
    file: UploadFile,
    context: AppContext = Depends(get_context),
):
    raw = _raw_dir(context)
    raw.mkdir(parents=True, exist_ok=True)
    dest = raw / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "filename": file.filename}

@router.delete("/.raw/{filename}")
async def delete_raw(
    filename: str,
    context: AppContext = Depends(get_context),
):
    raw = _raw_dir(context)
    fpath = raw / filename
    if fpath.exists():
        fpath.unlink()
    return {"ok": True}
```

Make sure the router is at the `knowledge` path prefix. Check the existing router prefix:

Read `cococat/routes/knowledge.py` first 30 lines to get the router name and prefix.

- [ ] **Step 2: Verify import structure**

Ensure `UploadFile` is imported from somewhere (check existing knowledge.py imports — it already uses uploads):
```python
from fastapi import UploadFile, File, Depends
```

- [ ] **Step 3: Test endpoints**

Run the backend and test:
```bash
curl -X GET http://localhost:8000/api/knowledge/.raw
# Expected: {"files": []}
```

### Task 14: Add i18n Keys

**Files:**
- Modify: `web-ui/src/i18n/zh.ts`
- Modify: `web-ui/src/i18n/en.ts`

- [ ] **Step 1: Add new keys to zh.ts**

Read the last few lines of zh.ts first, then append:

```typescript
  // Bookshelf
  "bookshelf.search": "搜索知识库...",
  "bookshelf.select_kb": "选择一个知识库",
  "bookshelf.new_kb": "新建知识库",

  // Raw Zone
  "raw.title": "Raw 暂存区",
  "raw.drop_hint": "拖拽文件或点击上传",
  "raw.organize": "让 agent 整理入库",
  "raw.uploading": "上传中...",
```

- [ ] **Step 2: Add same keys to en.ts**

Read en.ts. Append:
```typescript
  "bookshelf.search": "Search KB...",
  "bookshelf.select_kb": "Select a knowledge base",
  "bookshelf.new_kb": "New KB",

  "raw.title": "Raw Staging",
  "raw.drop_hint": "Drop files or click to upload",
  "raw.organize": "Ask agent to organize",
  "raw.uploading": "Uploading...",
```

- [ ] **Step 3: Verify build**

Run: `cd web-ui && npm run build 2>&1 | tail -5`
Expected: build succeeds

### Task 15: Cleanup & Final Verification

**Files:**
- Check: no stale imports remain
- Check: all routes work

- [ ] **Step 1: Remove remaining stale imports**

Search for imports of deleted files:
```bash
cd web-ui && grep -r "from.*OpDisplay\|from.*KbAdminFunc\|from.*KnowledgeView" src/
```
Expected: no results.

- [ ] **Step 2: Full build check**

Run: `cd web-ui && npm run build 2>&1`
Expected: no errors.

- [ ] **Step 3: Quick smoke test**

Run the dev server and manually verify:
- `/app/chat` renders chat overlay
- Click "knowledge" in left nav → navigates to `/app/knowledge`, chat collapses to rail
- Click "chat" in left nav → returns to `/app/chat`, chat overlays
- Bookshelf scrolls, 🔻 appears, search panel opens

- [ ] **Step 4: Commit all changes**

```bash
git add -A
git commit -m "feat: bookshelf & layout redesign — route-based nav, chat overlay/collapse, infinite bookshelf, doc renderer, raw zone, namecard animation"
```

---
