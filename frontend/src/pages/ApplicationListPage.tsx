import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { listApplications } from '../api'
import { ErrorBox, StageBadge } from '../components'
import { dayBoundary, formatDateTime } from '../format'
import { STAGES } from '../stages'
import type { ApplicationSummary, Page, StageValue } from '../types'

const PAGE_SIZE = 20

type Filters = { email: string; receipt: string; after: string; before: string }

type Result = { key: string; data?: Page<ApplicationSummary>; error?: Error }

function filtersFrom(params: URLSearchParams): Filters {
  return {
    email: params.get('email') ?? '',
    receipt: params.get('receipt') ?? '',
    after: params.get('after') ?? '',
    before: params.get('before') ?? '',
  }
}

export default function ApplicationListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const applied = filtersFrom(searchParams)
  const stage = (searchParams.get('stage') as StageValue | null) ?? ''

  const queryKey = searchParams.toString()
  // The result remembers which query it answers, so "loading" is derived:
  // a new query is loading until its own result arrives. Stale rows stay on
  // screen meanwhile instead of flashing empty.
  const [result, setResult] = useState<Result | null>(null)
  const loading = result?.key !== queryKey
  const data = result?.data ?? null
  const error = loading ? null : (result?.error ?? null)

  useEffect(() => {
    const params = new URLSearchParams(queryKey)
    let ignore = false
    listApplications({
      email: params.get('email') ?? undefined,
      receipt: params.get('receipt') ?? undefined,
      stage: (params.get('stage') as StageValue | null) ?? undefined,
      submitted_after: dayBoundary(params.get('after') ?? '', 'start'),
      submitted_before: dayBoundary(params.get('before') ?? '', 'end'),
      page: Math.max(1, Number(params.get('page')) || 1),
      page_size: PAGE_SIZE,
    })
      .then((page) => {
        if (!ignore) setResult({ key: queryKey, data: page })
      })
      .catch((err: Error) => {
        if (!ignore) setResult({ key: queryKey, error: err })
      })
    return () => {
      ignore = true
    }
  }, [queryKey])

  function applyFilters(filters: Filters) {
    const next = new URLSearchParams()
    if (stage) next.set('stage', stage)
    for (const [key, value] of Object.entries(filters)) {
      if (value.trim()) next.set(key, value.trim())
    }
    setSearchParams(next) // no page param, so back to page 1
  }

  function pickStage(value: StageValue | '') {
    const next = new URLSearchParams(searchParams)
    next.delete('page')
    if (value) next.set('stage', value)
    else next.delete('stage')
    setSearchParams(next)
  }

  function clearFilters() {
    setSearchParams(new URLSearchParams())
  }

  function goToPage(target: number) {
    const next = new URLSearchParams(searchParams)
    next.set('page', String(target))
    setSearchParams(next)
  }

  function open(id: number) {
    navigate(`/applications/${id}`, { state: { listSearch: location.search } })
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1
  const hasFilters = Boolean(stage) || Object.values(applied).some(Boolean)

  return (
    <>
      <div className="page-head">
        <h1>Applications</h1>
        {data && (
          <span className="muted">
            {data.count} {data.count === 1 ? 'applicant' : 'applicants'}
          </span>
        )}
      </div>

      <FilterForm
        key={queryKey} // remount on URL change (back button, shared link)
        initial={applied}
        onApply={applyFilters}
        onClear={hasFilters ? clearFilters : undefined}
      />

      <div className="stage-tabs" role="group" aria-label="Filter by stage">
        <button
          type="button"
          className={stage === '' ? 'tab active' : 'tab'}
          onClick={() => pickStage('')}
        >
          All stages
        </button>
        {STAGES.map((s) => (
          <button
            key={s.value}
            type="button"
            className={stage === s.value ? 'tab active' : 'tab'}
            onClick={() => pickStage(s.value)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {error && <ErrorBox error={error} />}

      <div className="card table-card">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Submitted</th>
              <th>Receipt</th>
              <th>Stage</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data && (
              <tr>
                <td colSpan={5} className="empty">
                  Loading…
                </td>
              </tr>
            )}
            {data && data.results.length === 0 && (
              <tr>
                <td colSpan={5} className="empty">
                  No applications match.
                </td>
              </tr>
            )}
            {data?.results.map((app) => (
              <tr key={app.id} className="row-link" onClick={() => open(app.id)}>
                <td>
                  <Link
                    to={`/applications/${app.id}`}
                    state={{ listSearch: location.search }}
                    onClick={(e) => e.stopPropagation()}
                    className="strong"
                  >
                    {app.name}
                  </Link>
                </td>
                <td>{app.email}</td>
                <td className="nowrap">{formatDateTime(app.submitted_at)}</td>
                <td className="mono truncate" title={app.receipt}>
                  {app.receipt}
                </td>
                <td>
                  <StageBadge stage={app.stage} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data && data.count > 0 && (
        <nav className="pager">
          <button
            className="btn btn-ghost"
            disabled={!data.previous || loading}
            onClick={() => goToPage(page - 1)}
          >
            ← Previous
          </button>
          <span className="muted">
            Page {page} of {totalPages}
          </span>
          <button
            className="btn btn-ghost"
            disabled={!data.next || loading}
            onClick={() => goToPage(page + 1)}
          >
            Next →
          </button>
        </nav>
      )}
    </>
  )
}

type FilterFormProps = {
  initial: Filters
  onApply: (filters: Filters) => void
  onClear?: () => void
}

// Edits a draft; filters only apply when the user submits. The parent keys
// this on the URL so a navigation resets the draft to what's applied.
function FilterForm({ initial, onApply, onClear }: FilterFormProps) {
  const [draft, setDraft] = useState<Filters>(initial)

  function submit(event: FormEvent) {
    event.preventDefault()
    onApply(draft)
  }

  return (
  <form className="card filters" onSubmit={submit}>
      <label>
        Email
        <input
          type="email"
          value={draft.email}
          onChange={(e) => setDraft({ ...draft, email: e.target.value })}
          placeholder="ada@example.com"
        />
      </label>
      <label>
        Receipt
        <input
          value={draft.receipt}
          onChange={(e) => setDraft({ ...draft, receipt: e.target.value })}
          placeholder="thank-you-from-b12-…"
        />
      </label>
      <label>
        Submitted after
        <input
          type="date"
          value={draft.after}
          onChange={(e) => setDraft({ ...draft, after: e.target.value })}
        />
      </label>
      <label>
        Submitted before
        <input
          type="date"
          value={draft.before}
          onChange={(e) => setDraft({ ...draft, before: e.target.value })}
        />
      </label>
      <div className="filter-actions">
        <button type="submit" className="btn btn-primary">
          Apply filters
        </button>
        {onClear && (
          <button type="button" className="btn btn-ghost" onClick={onClear}>
            Clear
          </button>
        )}
      </div>
    </form>
  )
}
