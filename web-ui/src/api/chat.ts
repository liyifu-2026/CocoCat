import { api } from "./client"

export interface GroupMember {
  id: string
  name: string
  role: string
}

export interface ChatGroup {
  id: string
  name: string
  announcement: string
  created_at: string
  is_default: boolean
  members: GroupMember[]
}

export interface ChatMessage {
  from: string
  content: string
  timestamp: string
  priority_score?: number
  token_count?: number
  mentions: string[]
}

export interface AgentContext {
  messages: ChatMessage[]
  digest: string
}

export const chatApi = {
  listGroups: () => api.get<{ groups: ChatGroup[] }>("/chat/groups"),
  getGroup: (id: string) => api.get<ChatGroup>(`/chat/groups/${id}`),
  createGroup: (name: string, members: { id: string; name: string; role: string }[], announcement?: string) =>
    api.post<{ group: ChatGroup }>("/chat/groups", { name, members, announcement }),
  updateGroup: (id: string, body: Record<string, string>) =>
    api.patch<{ group: ChatGroup }>(`/chat/groups/${id}`, body),
  addMember: (groupId: string, agentId: string, name: string) =>
    api.post<{ group: ChatGroup }>(`/chat/groups/${groupId}/members`, { agent_id: agentId, name }),
  removeMember: (groupId: string, agentId: string) =>
    api.delete<{ group: ChatGroup }>(`/chat/groups/${groupId}/members/${agentId}`),
  deleteGroup: (groupId: string) =>
    api.delete<{ status: string }>(`/chat/groups/${groupId}`),
  sendMessage: (groupId: string, content: string, from = "admin") =>
    api.post<{ message: ChatMessage }>(`/chat/groups/${groupId}/messages`, { content, from }),
  getMessages: (groupId: string, limit = 100) =>
    api.get<{ messages: ChatMessage[] }>(`/chat/groups/${groupId}/messages?limit=${limit}`),
}
