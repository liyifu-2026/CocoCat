import { api } from "./client"

export interface Agent {
  id: string
  name: string
  enabled: boolean
  scene: string
  status: string
}

export interface UsageEntry {
  agent_id: string
  timestamp?: string
  input_tokens?: number
  output_tokens?: number
  total_tokens: number
  iterations: number
}

export interface AgentDetail {
  id: string
  name: string
  enabled: boolean
  scene: string
  interpreter: string
  script: string
}

export interface AgentProfile {
  role: string
  objective: string
  traits: string[]
  background: string
  rules: string[]
}

export interface AgentSkills {
  public: string[]
  private: string[]
}

export interface AgentMemory {
  content: string
}

export interface HistoryEntry {
  timestamp: string
  prompt: string
  response_summary: string
  iterations: number
}

export interface AgentDisplay {
  nickname: string
  avatar: string
  color: string
  gender?: string
}

export const agentsApi = {
  list: () => api.get<{ agents: Agent[] }>("/agents"),
  usage: (limit = 10) => api.get<{ usage: UsageEntry[] }>(`/usage?limit=${limit}`),
  get: (id: string) => api.get<AgentDetail>(`/agents/${id}`),
  profile: (id: string) => api.get<AgentProfile>(`/agents/${id}/profile`),
  skills: (id: string) => api.get<{ skills: any[] }>(`/agents/${id}/skills`),
  memory: (id: string) => api.get<AgentMemory>(`/agents/${id}/memory`),
  history: (id: string, limit = 50) =>
    api.get<{ entries: HistoryEntry[] }>(`/agents/${id}/history?limit=${limit}`),
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<{ status: string }>(`/agents/${id}`, body),
  display: (id: string) => api.get<AgentDisplay>(`/agents/${id}/display`),
  listDisplays: () => api.get<Record<string, AgentDisplay>>("/agents/display"),
  updateDisplay: (id: string, display: AgentDisplay) =>
    api.put<{ display: AgentDisplay }>(`/agents/${id}/display`, display),
  delete: (id: string) =>
    api.delete<{ status: string }>(`/agents/${id}`),
  warehouseList: () => api.get<{ skills: any[] }>("/skills/warehouse"),
  assignSkills: (id: string, skillIds: string[]) =>
    api.post<{ status: string }>(`/agents/${id}/skills`, { skill_ids: skillIds }),
  capabilities: () => api.get<{ agents: any[] }>("/agents/capabilities"),
}
