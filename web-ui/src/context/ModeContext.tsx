import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

interface ModeInfo {
  id: string
  name: string
  description: string
}

interface ModeContextValue {
  currentMode: string
  modes: ModeInfo[]
  setMode: (mode: string) => void
}

const ModeContext = createContext<ModeContextValue>({
  currentMode: "default",
  modes: [],
  setMode: () => {},
})

export function ModeProvider({ children }: { children: ReactNode }) {
  const [currentMode, setCurrentMode] = useState("default")
  const [modes, setModes] = useState<ModeInfo[]>([
    { id: "default", name: "Coco", description: "日常助手" },
    { id: "kb-admin", name: "KB 管理", description: "知识库管理" },
  ])

  useEffect(() => {
    fetch("/api/modes")
      .then(r => r.json())
      .then((data: ModeInfo[]) => {
        if (data?.length) setModes(data)
      })
      .catch(() => {})
  }, [])

  const setMode = (mode: string) => {
    if (modes.some(m => m.id === mode)) {
      setCurrentMode(mode)
    }
  }

  return (
    <ModeContext.Provider value={{ currentMode, modes, setMode }}>
      {children}
    </ModeContext.Provider>
  )
}

export function useMode() {
  return useContext(ModeContext)
}
