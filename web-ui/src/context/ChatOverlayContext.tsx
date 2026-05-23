import { createContext, useContext, useState, useCallback, type ReactNode } from "react"

type ChatState = "overlay" | "collapsed"

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

const ChatOverlayCtx = createContext<ChatOverlayValue>({
  chatState: "overlay",
  setChatState: () => {},
  toggleChat: () => {},
  filePreview: null,
  openFilePreview: () => {},
  closeFilePreview: () => {},
})

export function ChatOverlayProvider({ children }: { children: ReactNode }) {
  const [chatState, setChatState] = useState<ChatState>("overlay")
  const [filePreview, setFilePreview] = useState<FilePreview | null>(null)

  const toggleChat = useCallback(() => {
    setChatState(prev => prev === "overlay" ? "collapsed" : "overlay")
  }, [])

  const openFilePreview = useCallback((fp: FilePreview) => {
    setFilePreview(fp)
    setChatState("collapsed")
  }, [])

  const closeFilePreview = useCallback(() => {
    setFilePreview(null)
  }, [])

  return (
    <ChatOverlayCtx.Provider value={{ chatState, setChatState, toggleChat, filePreview, openFilePreview, closeFilePreview }}>
      {children}
    </ChatOverlayCtx.Provider>
  )
}

export function useChatOverlay() {
  return useContext(ChatOverlayCtx)
}
