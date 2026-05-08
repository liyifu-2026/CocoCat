import { api } from "./client"

export interface ScheduleTask {
  id: number
  task: string
  assigned_to: string
  status: string
  task_type?: "one_time" | "recurring_template" | "recurring_instance"
  recurrence?: string
  parent_task_id?: number
  created_at: string
  started_at?: string
  completed_at?: string
  result?: string
  error?: string
}

export interface CreateTaskRequest {
  task: string
  assigned_to: string
  task_type?: "one_time" | "recurring_template"
  recurrence?: number
}

export const scheduleApi = {
  get: () => api.get<{ tasks: ScheduleTask[] }>("/schedule"),
  create: (req: CreateTaskRequest) =>
    api.post<{ task: ScheduleTask }>("/schedule/tasks", req),
  update: (taskId: number, body: Record<string, unknown>) =>
    api.patch<{ task: ScheduleTask }>(`/schedule/tasks/${taskId}`, body),
  delete: (taskId: number) =>
    api.delete<{ status: string }>(`/schedule/tasks/${taskId}`),
}
