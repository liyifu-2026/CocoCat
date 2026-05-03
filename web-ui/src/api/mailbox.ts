import { api } from "./client"

export interface MailboxSummary {
  agent_id: string
  name: string
  unread: number
  latest: { from: string; content: string; timestamp: string; status: string } | null
}

export interface MailMessage {
  from: string
  content: string
  timestamp: string
  status: string
}

export const mailboxApi = {
  list: () => api.get<{ mailboxes: MailboxSummary[] }>("/mailbox"),
  getMessages: (agentId: string) => api.get<{ messages: MailMessage[] }>(`/mailbox/${agentId}`),
  send: (agentId: string, content: string) =>
    api.post<{ status: string }>(`/mailbox/${agentId}`, { content }),
  markRead: (agentId: string) =>
    api.post<{ status: string }>(`/mailbox/${agentId}/read`, {}),
}
