import { api } from "./client"

export interface KnowledgeBase {
  id: string
  path: string
}

export const knowledgeApi = {
  list: () => api.get<{ kbs: KnowledgeBase[] }>("/knowledge"),
}
