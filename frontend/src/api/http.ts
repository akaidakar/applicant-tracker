// The real client: calls the Django API on the same origin with the session cookie.
import type {
  ApplicationDetail,
  ApplicationSummary,
  ListParams,
  Note,
  Page,
  StageValue,
} from '../types'
import { ApiError } from './errors'

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

// Our views answer with {message}, DRF's own errors with {detail}.
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (body.message) return body.message
    if (body.detail) return body.detail
    if (Array.isArray(body.details)) return body.details.join('; ')
  } catch {
    // Not JSON, fall through.
  }
  return `Request failed with status ${response.status}`
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.method && init.method !== 'GET') {
    headers.set('Content-Type', 'application/json')
    headers.set('X-CSRFToken', csrfToken())
  }
  const response = await fetch(path, { ...init, headers, credentials: 'same-origin' })
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return response.json() as Promise<T>
}

export function listApplications(params: ListParams): Promise<Page<ApplicationSummary>> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  return request(`/api/applications?${query}`)
}

export function getApplication(id: string | number): Promise<ApplicationDetail> {
  return request(`/api/applications/${id}`)
}

export function addNote(
  id: string | number,
  content: string,
): Promise<Note & { stage: ApplicationDetail['stage'] }> {
  return request(`/api/applications/${id}/notes`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

export function changeStage(id: string | number, stage: StageValue): Promise<ApplicationDetail> {
  return request(`/api/applications/${id}/stage`, {
    method: 'POST',
    body: JSON.stringify({ stage }),
  })
}
