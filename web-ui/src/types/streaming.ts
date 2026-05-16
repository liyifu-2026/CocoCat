export interface StreamEvent {
  event_type: string
  content: string
  name?: string
  input?: string
  status?: string
  result?: string
}

export interface StreamState {
  task_uuid: string
  event: string
  status: string
  content?: string
  stream_event?: StreamEvent
  updatedAt: number
  error?: string
}
