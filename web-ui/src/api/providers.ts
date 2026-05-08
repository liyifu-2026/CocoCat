import { api } from "./client"

export interface ProviderInfo {
  name: string
  keywords: string[]
  display_name?: string
  api_base: string
  default_model: string
  has_key: boolean
  key_masked: string
}

export interface ModelInfo {
  id: string
  name?: string
  provider?: string
}

export interface AgentModelConfig {
  provider: string
  model: string
  reasoning_effort: string
}

export const providersApi = {
  // Provider config
  list: () => api.get<{ providers: ProviderInfo[] }>("/providers"),

  get: (name: string) => api.get<ProviderInfo & { key_masked: string }>(`/providers/${name}`),

  update: (name: string, data: { api_base?: string; default_model?: string; api_key?: string }) =>
    api.put<{ status: string }>(`/providers/${name}`, data),

  test: (name: string) =>
    api.post<{ status: string; models?: string[]; message?: string }>(`/providers/${name}/test`, {}),

  // Fetch models live from a specific provider
  fetchProviderModels: (name: string) =>
    api.get<{ models: ModelInfo[]; source: string; error?: string }>(`/providers/${name}/models/fetch`),

  // Model catalog
  listModels: (provider?: string) =>
    api.get<{ models: ModelInfo[] }>(`/models${provider ? `?provider=${provider}` : ""}`),

  refreshModels: () =>
    api.post<{ status: string }>("/models/refresh", {}),

  // Agent model assignment
  getAgentModel: (agentId: string) =>
    api.get<AgentModelConfig>(`/agents/${agentId}/model`),

  setAgentModel: (agentId: string, data: AgentModelConfig) =>
    api.put<{ status: string }>(`/agents/${agentId}/model`, data),
}
