import type { Stage, StageValue } from './types'

// Mirrors Stage in apply/models.py. The server validates every move; the
// frontend uses this for the stage picker and the confirm before rejecting.
export const STAGES: Stage[] = [
  { value: 'new', label: 'New' },
  { value: 'phone_screen_scheduled', label: 'Phone screen scheduled' },
  { value: 'interview_scheduled', label: 'Interview scheduled' },
  { value: 'hired', label: 'Hired' },
  { value: 'rejected', label: 'Rejected' },
]

// Nothing comes after Rejected, so it's the one move that can't be undone.
export const FINAL: StageValue = 'rejected'
