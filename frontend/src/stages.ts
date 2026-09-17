import type { Stage, StageValue } from './types'

// Mirrors Stage and TERMINAL in apply/models.py. The server validates every
// move; the frontend uses this for the stage picker and the terminal confirm.
export const STAGES: Stage[] = [
  { value: 'new', label: 'New' },
  { value: 'phone_screen_scheduled', label: 'Phone screen scheduled' },
  { value: 'interview_scheduled', label: 'Interview scheduled' },
  { value: 'hired', label: 'Hired' },
  { value: 'rejected', label: 'Rejected' },
]

export const TERMINAL: StageValue[] = ['hired', 'rejected']
