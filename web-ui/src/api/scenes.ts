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
}
