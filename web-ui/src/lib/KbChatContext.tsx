import { createContext, useState, useCallback, type ReactNode } from "react"

export interface ToolMessage {
  type: "tool"
  id: string
  name: string
  status: "running" | "done" | "error"
  arguments?: string
  result?: string
  elapsed?: number
}

export interface ChatMessage {
  type: "chat"
  role: "user" | "assistant"
  content: string
}

export type Message = ChatMessage | ToolMessage

interface KbChatContextType {
  messages: Message[]
  loading: boolean
  addMessage: (msg: ChatMessage) => void
  addToolMessage: (tool: ToolMessage) => void
  appendToLast: (text: string) => void
  finalizeLast: (text: string) => void
  setLoading: (v: boolean) => void
  clearMessages: () => void
}

export const KbChatContext = createContext<KbChatContextType | null>(null)

export function KbChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages(prev => [...prev, msg])
  }, [])

  const addToolMessage = useCallback((tool: ToolMessage) => {
    setMessages(prev => [...prev, tool])
  }, [])

  const appendToLast = useCallback((text: string) => {
    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.type === "chat") {
        updated[updated.length - 1] = { ...last, content: (last as ChatMessage).content + text }
      }
      return updated
    })
  }, [])

  const finalizeLast = useCallback((text: string) => {
    setMessages(prev => {
      const updated = [...prev]
      const last = updated[updated.length - 1]
      if (last && last.type === "chat") {
        updated[updated.length - 1] = { ...last, content: text }
      }
      return updated
    })
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return (
    <KbChatContext.Provider value={{
      messages, loading, addMessage, addToolMessage,
      appendToLast, finalizeLast, setLoading, clearMessages,
    }}>
      {children}
    </KbChatContext.Provider>
  )
}
