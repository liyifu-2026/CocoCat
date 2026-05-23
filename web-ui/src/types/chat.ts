export interface ToolCallRecord {
  id: string
  name: string
  status: "running" | "done" | "error"
  toolCallId?: string
  arguments?: string
  result?: string
  elapsed?: number
}

export interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  tools?: ToolCallRecord[]
  reasoningText?: string
  timestamp: number
}

export interface Session {
  id: string
  title: string
  messages: Message[]
  createdAt: number
}
