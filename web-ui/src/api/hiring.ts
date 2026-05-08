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
  created_at?: string
}

export interface HirePlanRequest {
  position: string
  skills?: string
  responsibilities?: string
  traits?: string
  count?: number
}

export interface HirePlanResponse {
  status: string
  task_uuid: string
}

export const hiringApi = {
  listPending: () => api.get<{ pending: PendingHire[] }>("/hiring/pending"),
  listApproved: () => api.get<{ approved: PendingHire[] }>("/hiring/approved"),
  listRejected: () => api.get<{ rejected: PendingHire[] }>("/hiring/rejected"),
  approve: (hireId: string, profile?: Record<string, unknown>) =>
    api.post<{ status: string; hire_id: string }>(`/hiring/pending/${hireId}/approve`, profile ?? {}),
  reject: (hireId: string) =>
    api.post<{ status: string; hire_id: string }>(`/hiring/pending/${hireId}/reject`, {}),
  createPlan: (data: HirePlanRequest) =>
    api.post<HirePlanResponse>("/hiring/plan", data),
}
