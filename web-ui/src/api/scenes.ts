import { api } from "./client"

export interface Scene {
  id: string
  context: string
  mounted_kbs: string[]
  env_skills: string[]
  roster: string[]
}

export const scenesApi = {
  list: () => api.get<{ scenes: Scene[] }>("/scenes"),
  create: (id: string, context?: string) =>
    api.post<{ status: string; scene_id: string }>("/scenes", { id, context }),
  delete: (sceneId: string) =>
    api.delete<{ status: string }>(`/scenes/${sceneId}`),
  updateContext: (sceneId: string, context: string) =>
    api.patch<{ status: string }>(`/scenes/${sceneId}/context`, { context }),
  updateKbs: (sceneId: string, mounted: string[]) =>
    api.patch<{ status: string; mounted: string[] }>(`/scenes/${sceneId}/kbs`, { mounted }),
  updateRoster: (sceneId: string, agents: string[]) =>
    api.patch<{ status: string; agents: string[] }>(`/scenes/${sceneId}/roster`, { agents }),
  updateSkills: (sceneId: string, env_skills: string[]) =>
    api.patch<{ status: string; env_skills: string[] }>(`/scenes/${sceneId}/skills`, { env_skills }),
}
