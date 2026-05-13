import { createContext, useContext, useState, useCallback, type ReactNode } from "react"

interface PanelContextType {
  content: ReactNode | null
  visible: boolean
  openPanel: (content: ReactNode) => void
  closePanel: () => void
}

const PanelContext = createContext<PanelContextType | null>(null)

export function PanelProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<ReactNode | null>(null)

  const openPanel = useCallback((content: ReactNode) => setContent(content), [])
  const closePanel = useCallback(() => setContent(null), [])

  return (
    <PanelContext.Provider value={{ content, visible: content !== null, openPanel, closePanel }}>
      {children}
    </PanelContext.Provider>
  )
}

export function usePanel() {
  const ctx = useContext(PanelContext)
  if (!ctx) throw new Error("usePanel must be used within PanelProvider")
  return ctx
}
