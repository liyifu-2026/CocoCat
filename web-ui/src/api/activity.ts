import { api } from "./client"

export interface ActivityEntry {
  type: "heartbeat_tick" | "mailbox_msg" | "schedule_task"
  agent_id: string
  agent_name?: string
  ts: string
  content?: string
  result?: string
  sender?: string
  task_id?: number
  deliverable?: boolean
  notified?: boolean
  detail?: string
}

export const activityApi = {
  list: (limit = 50) =>
    api.get<{ activities: ActivityEntry[] }>(`/activity?limit=${limit}`),
}
