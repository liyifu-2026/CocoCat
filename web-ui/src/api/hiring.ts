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

export interface HirePlanRequest {
  position: string
  skills?: string
  responsibilities?: string
  traits?: string
  count?: number
}

export interface HirePlanResponse {
  plan_uuid: string
  status: string
}

export const hiringApi = {
  listPending: () => api.get<{ pending: PendingHire[] }>("/hiring/pending"),
  approve: (hireId: string, profile?: Record<string, unknown>) =>
    api.post<{ status: string; hire_id: string }>(`/hiring/${hireId}/approve`, profile ?? {}),
  reject: (hireId: string) =>
    api.post<{ status: string; hire_id: string }>(`/hiring/${hireId}/reject`, {}),
  createPlan: (data: HirePlanRequest) =>
    api.post<HirePlanResponse>("/hiring/plan", data),
}
