// Shapes of the /api responses. See the API section of the root README.

export type StageValue =
  | 'new'
  | 'phone_screen_scheduled'
  | 'interview_scheduled'
  | 'hired'
  | 'rejected'

export type Stage = { value: StageValue; label: string }

export type ApplicationSummary = {
  id: number
  name: string
  email: string
  submitted_at: string
  receipt: string
  stage: Stage
}

export type Page<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type Note = {
  id: number
  content: string
  created_at: string
}

export type HistoryEntry = {
  stage: Stage
  entered_at: string
  notes: Note[]
}

export type ApplicationDetail = ApplicationSummary & {
  resume_link: string
  repository_link: string
  action_run_link: string
  allowed_next_stages: Stage[]
  history: HistoryEntry[]
}

export type ListParams = {
  email?: string
  receipt?: string
  stage?: StageValue
  submitted_after?: string
  submitted_before?: string
  page?: number
  page_size?: number
}
