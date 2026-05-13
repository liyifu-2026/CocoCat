import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react"

const DEFAULT_PATHS = [
  "/dashboard", "/chat", "/agents", "/scenes",
]

const STORAGE_KEY = "cococat-sidebar-nav-config"

function loadConfig(): { order: string[]; hidden: string[] } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (
        Array.isArray(parsed?.order) &&
        Array.isArray(parsed?.hidden)
      ) {
        return { order: parsed.order, hidden: parsed.hidden }
      }
    }
  } catch { /* ignore */ }
  return { order: [...DEFAULT_PATHS], hidden: [] }
}

function saveConfig(order: string[], hidden: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ order, hidden }))
  } catch { /* ignore */ }
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

  const [config, setConfig] = useState(() => {
    if (typeof localStorage === "undefined") return { order: [...DEFAULT_PATHS], hidden: [] }
    return loadConfig()
  })
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
