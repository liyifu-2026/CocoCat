import { api } from "./client"

export interface ChannelInfo {
  id: string
  name: string
  description: string
  config_schema: Record<string, { type: string; description: string; default: string }>
}

export interface EntryConfig {
  channel: string
  config: Record<string, string>
  enabled: boolean
}

export const entriesApi = {
  listChannels: () => api.get<{ channels: ChannelInfo[] }>("/channels"),

  // Agent entries
  getAgentEntries: (agentId: string) => api.get<{ entries: EntryConfig[] }>(`/agents/${agentId}/entries`),
  updateAgentEntries: (agentId: string, entries: EntryConfig[]) =>
    api.put<{ entries: EntryConfig[] }>(`/agents/${agentId}/entries`, { entries }),

  // Scene entries
  getSceneEntries: (sceneId: string) => api.get<{ entries: EntryConfig[] }>(`/scenes/${sceneId}/entries`),
  updateSceneEntries: (sceneId: string, entries: EntryConfig[]) =>
    api.put<{ entries: EntryConfig[] }>(`/scenes/${sceneId}/entries`, { entries }),
}
