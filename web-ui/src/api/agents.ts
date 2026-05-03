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

export const agentsApi = {
  list: () => api.get<{ agents: Agent[] }>("/agents"),
  usage: (limit = 10) => api.get<{ usage: UsageEntry[] }>(`/usage?limit=${limit}`),
}
