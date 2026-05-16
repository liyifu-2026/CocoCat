export interface Task {
  id: string
  status: string
  result?: string
  error?: string
}

export interface Stage {
  id: string
  name?: string
  status?: string
  tasks: Task[]
  parallel?: boolean
  depends_on?: string[]
}

export interface DagRun {
  run_id: string
  created_by?: string
  status: string
  stages: Stage[]
}

export type Status = "done" | "running" | "failed" | "pending"
