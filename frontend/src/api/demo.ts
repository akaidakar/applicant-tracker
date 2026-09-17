// The demo client: the same four calls as http.ts, answered from a copy of
// the seed data held in localStorage. It exists so the GitHub Pages build can
// be clicked through without a Django server. The rules it applies (forward
// only, terminal stages, blank notes) mirror apply/views.py, but the server
// remains the source of truth in the real app.
import seed from '../demo/seed.json'
import { allowedNextStages, STAGES } from '../stages'
import type {
  ApplicationDetail,
  ApplicationSummary,
  ListParams,
  Note,
  Page,
  StageValue,
} from '../types'
import { ApiError } from './errors'

const STORAGE_KEY = 'b12-applicants-demo-v1'
const LATENCY_MS = 150

type Store = { applications: ApplicationDetail[]; nextNoteId: number }

function freshStore(): Store {
  const applications = structuredClone(seed) as ApplicationDetail[]
  const noteIds = applications.flatMap((a) => a.history.flatMap((h) => h.notes.map((n) => n.id)))
  return { applications, nextNoteId: Math.max(0, ...noteIds) + 1 }
}

function load(): Store {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as Store
  } catch {
    // Private window or blocked storage: fall through to the seed.
  }
  return freshStore()
}

function save(store: Store) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store))
  } catch {
    // Storage unavailable: changes last for this page load only.
  }
}

export function reset() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Nothing stored, nothing to remove.
  }
}

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS))
}

function find(store: Store, id: string | number): ApplicationDetail {
  const application = store.applications.find((a) => a.id === Number(id))
  if (!application) throw new ApiError(404, 'No Application matches the given query.')
  return application
}

function summary(a: ApplicationDetail): ApplicationSummary {
  const { id, name, email, submitted_at, receipt, stage } = a
  return { id, name, email, submitted_at, receipt, stage }
}

export function listApplications(params: ListParams): Promise<Page<ApplicationSummary>> {
  const store = load()
  let rows = store.applications
  if (params.email) rows = rows.filter((a) => a.email === params.email)
  if (params.receipt) rows = rows.filter((a) => a.receipt === params.receipt)
  if (params.submitted_after) {
    const after = Date.parse(params.submitted_after)
    rows = rows.filter((a) => Date.parse(a.submitted_at) >= after)
  }
  if (params.submitted_before) {
    const before = Date.parse(params.submitted_before)
    rows = rows.filter((a) => Date.parse(a.submitted_at) <= before)
  }
  rows = [...rows].sort(
    (a, b) => Date.parse(b.submitted_at) - Date.parse(a.submitted_at) || b.id - a.id,
  )

  const pageSize = params.page_size ?? 20
  const page = params.page ?? 1
  const start = (page - 1) * pageSize
  const results = rows.slice(start, start + pageSize).map(summary)
  return delay({
    count: rows.length,
    next: start + pageSize < rows.length ? `?page=${page + 1}` : null,
    previous: page > 1 ? `?page=${page - 1}` : null,
    results,
  })
}

export function getApplication(id: string | number): Promise<ApplicationDetail> {
  return delay(structuredClone(find(load(), id)))
}

export function addNote(
  id: string | number,
  content: string,
): Promise<Note & { stage: ApplicationDetail['stage'] }> {
  if (!content.trim()) throw new ApiError(400, 'content is required and cannot be blank.')
  const store = load()
  const application = find(store, id)
  const entry = application.history[application.history.length - 1]
  const note: Note = {
    id: store.nextNoteId++,
    content,
    created_at: new Date().toISOString(),
  }
  entry.notes.push(note)
  save(store)
  return delay({ ...note, stage: entry.stage })
}

export function changeStage(
  id: string | number,
  stage: StageValue,
): Promise<ApplicationDetail> {
  const store = load()
  const application = find(store, id)
  const allowed = allowedNextStages(application.stage.value)
  const target = allowed.find((s) => s.value === stage)
  if (!target) {
    const current = application.stage.label
    const message =
      allowed.length === 0
        ? `${current} is a final stage. The stage can't change.`
        : `Can't move from ${current} to ${labelOf(stage)}. ` +
          `Allowed: ${allowed.map((s) => s.label).join(', ')}.`
    throw new ApiError(400, message)
  }
  application.stage = target
  application.allowed_next_stages = allowedNextStages(target.value)
  application.history.push({ stage: target, entered_at: new Date().toISOString(), notes: [] })
  save(store)
  return delay(structuredClone(application))
}

function labelOf(value: StageValue): string {
  return STAGES.find((s) => s.value === value)?.label ?? value
}
