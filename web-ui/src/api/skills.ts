import { api } from "./client"

export interface Skill {
  name: string
  title: string
}

export const skillsApi = {
  list: () => api.get<{ public: Skill[]; private: Skill[] }>("/skills"),
}
