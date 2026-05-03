import { api } from "./client"

export interface Agent {
  id: string
  name: string
  enabled: boolean
  scene: string
}

export interface UsageEntry {
  agent_id: string
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

export const agentsApi = {
  list: () => api.get<{ agents: Agent[] }>("/agents"),
  usage: (limit = 10) => api.get<{ usage: UsageEntry[] }>(`/usage?limit=${limit}`),
  get: (id: string) => api.get<AgentDetail>(`/agents/${id}`),
  profile: (id: string) => api.get<AgentProfile>(`/agents/${id}/profile`),
  skills: (id: string) => api.get<AgentSkills>(`/agents/${id}/skills`),
  memory: (id: string) => api.get<AgentMemory>(`/agents/${id}/memory`),
  history: (id: string, limit = 50) =>
    api.get<{ entries: HistoryEntry[] }>(`/agents/${id}/history?limit=${limit}`),
}
