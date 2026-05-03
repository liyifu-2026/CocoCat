import { api } from "./client"

export interface PendingHire {
  id: string
  name: string
  scene: string
  profile: {
    role: string
    objective: string
    traits: string[]
    background: string
    rules: string[]
  }
  status: string
}

export const hiringApi = {
  listPending: () => api.get<{ pending: PendingHire[] }>("/hiring/pending"),
  approve: (hireId: string, profile?: Record<string, unknown>) =>
    api.post<{ status: string; hire_id: string }>(`/hiring/pending/${hireId}/approve`, profile ?? {}),
  reject: (hireId: string) =>
    api.post<{ status: string; hire_id: string }>(`/hiring/pending/${hireId}/reject`, {}),
}
