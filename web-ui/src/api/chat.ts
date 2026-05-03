import { api } from "./client"

export interface ChatMessage {
  timestamp: string
  from: string
  to: string
  content: string
  message_type: string
}

export const chatApi = {
  list: (limit = 50) => api.get<{ messages: ChatMessage[] }>(`/chat?limit=${limit}`),
}
