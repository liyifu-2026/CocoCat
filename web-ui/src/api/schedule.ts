import { api } from "./client"

export interface ScheduleTask {
  id: number
  task: string
  assigned_to: string
  status: string
  created_at: string
  result?: string
}

export const scheduleApi = {
  get: () => api.get<{ tasks: ScheduleTask[] }>("/schedule"),
  create: (task: string, assignedTo: string) =>
    api.post<{ task: ScheduleTask }>("/schedule/tasks", { task, assigned_to: assignedTo }),
  update: (taskId: number, body: Record<string, unknown>) =>
    api.patch<{ task: ScheduleTask }>(`/schedule/tasks/${taskId}`, body),
  delete: (taskId: number) =>
    api.delete<{ status: string }>(`/schedule/tasks/${taskId}`),
}
