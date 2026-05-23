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
