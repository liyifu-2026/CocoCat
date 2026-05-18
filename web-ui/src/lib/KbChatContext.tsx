import { createContext, useState, useCallback, useMemo, useEffect, type ReactNode } from "react"

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
  sessionId: string
  addMessage: (msg: ChatMessage) => void
  addToolMessage: (tool: ToolMessage) => void
  appendToLast: (text: string) => void
  finalizeLast: (text: string) => void
  setLoading: (v: boolean) => void
  clearMessages: () => void
  newSession: () => void
}

export const KbChatContext = createContext<KbChatContextType | null>(null)

function loadSessionId(): string {
  const stored = localStorage.getItem("kb-chat-session")
  if (stored) return stored
  const id = crypto.randomUUID?.() ?? Date.now().toString(36)
  localStorage.setItem("kb-chat-session", id)
  return id
}

export function KbChatProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState(loadSessionId)
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  // Load history on mount / session change
  useEffect(() => {
    fetch(`/api/kb-chat/history?session_id=${sessionId}`)
      .then(r => r.json())
      .then(d => {
        if (d.messages?.length) {
          setMessages(d.messages.map((m: { role: string; content: string }) => ({
            type: "chat" as const,
            role: m.role as "user" | "assistant",
            content: m.content,
          })))
        }
      })
      .catch(() => {})
  }, [sessionId])

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

  const newSession = useCallback(() => {
    const id = crypto.randomUUID?.() ?? Date.now().toString(36)
    localStorage.setItem("kb-chat-session", id)
    setSessionId(id)
    setMessages([])
  }, [])

  const value = useMemo(() => ({
    messages, loading, sessionId, addMessage, addToolMessage,
    appendToLast, finalizeLast, setLoading, clearMessages, newSession,
  }), [messages, loading, sessionId, addMessage, addToolMessage, appendToLast, finalizeLast, setLoading, clearMessages, newSession])

  return (
    <KbChatContext.Provider value={value}>
      {children}
    </KbChatContext.Provider>
  )
}
