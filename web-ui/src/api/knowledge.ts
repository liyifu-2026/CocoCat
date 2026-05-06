import { api } from "./client"

export interface KnowledgeBase {
  id: string
}

export interface KBDetail {
  id: string
  purpose?: string
  schema?: string
  index?: string
}

export interface WikiPage {
  name: string
  title: string
  type: string
  tags: string[]
  path: string
}

export interface WikiPageContent {
  frontmatter: Record<string, string>
  body: string
}

export interface SearchResult {
  name: string
  title: string
  type: string
  path: string
  snippet: string
}

export const knowledgeApi = {
  list: () => api.get<{ kbs: KnowledgeBase[] }>("/knowledge"),
  get: (kbId: string) => api.get<KBDetail>(`/knowledge/${kbId}`),
  listWiki: (kbId: string) => api.get<{ pages: WikiPage[] }>(`/knowledge/${kbId}/wiki`),
  getWikiPage: (kbId: string, type: string, name: string) =>
    api.get<WikiPageContent>(`/knowledge/${kbId}/wiki/${type}/${name}`),
  search: (kbId: string, q: string) =>
    api.get<{ results: SearchResult[] }>(`/knowledge/${kbId}/search?q=${encodeURIComponent(q)}`),
  upload: (kbName: string, filename: string, content: string) =>
    api.post<{ status: string; task_uuid: string; kb_name: string }>("/knowledge/upload", { kb_name: kbName, filename, content }),
  process: (kbName: string, filename: string) =>
    api.post<{ status: string; task_uuid: string }>(`/knowledge/${kbName}/process`, { filename }),
  tasks: (kbName: string) =>
    api.get<{ tasks: any[] }>(`/knowledge/${kbName}/tasks`),
}
