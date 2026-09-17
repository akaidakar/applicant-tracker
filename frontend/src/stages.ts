import type { Stage, StageValue } from './types'

// Mirrors apply/models.py. The server validates every move; the frontend
// only uses this for the demo client and the "can't be undone" confirm.
export const STAGES: Stage[] = [
  { value: 'new', label: 'New' },
  { value: 'phone_screen_scheduled', label: 'Phone screen scheduled' },
  { value: 'interview_scheduled', label: 'Interview scheduled' },
  { value: 'hired', label: 'Hired' },
  { value: 'rejected', label: 'Rejected' },
]

export const TERMINAL: StageValue[] = ['hired', 'rejected']

export function allowedNextStages(current: StageValue): Stage[] {
  if (TERMINAL.includes(current)) return []
  const index = STAGES.findIndex((s) => s.value === current)
  return STAGES.slice(index + 1)
}
