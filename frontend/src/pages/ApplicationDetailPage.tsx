import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { addNote, changeStage, getApplication } from '../api'
import { ErrorBox, StageBadge } from '../components'
import { formatDateTime } from '../format'
import { TERMINAL } from '../stages'
import type { ApplicationDetail, StageValue } from '../types'

type Loaded = { id: string; app?: ApplicationDetail; error?: Error }

export default function ApplicationDetailPage() {
  const { id = '' } = useParams()
  const location = useLocation()
  const listSearch = (location.state as { listSearch?: string } | null)?.listSearch ?? ''

  // Keyed on the id so switching applications shows "Loading" instead of
  // the previous applicant, with no reset needed in the effect.
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const app = loaded?.id === id ? (loaded.app ?? null) : null
  const loadError = loaded?.id === id ? (loaded.error ?? null) : null

  const [nextStage, setNextStage] = useState<StageValue | ''>('')
  const [stageBusy, setStageBusy] = useState(false)
  const [stageError, setStageError] = useState<string | null>(null)

  const [note, setNote] = useState('')
  const [noteBusy, setNoteBusy] = useState(false)
  const [noteError, setNoteError] = useState<string | null>(null)

  // Counts requests so a slow response for a previous id can't overwrite
  // the application the user navigated to since.
  const requestId = useRef(0)

  const show = useCallback(
    (fresh: ApplicationDetail) => {
      setLoaded({ id, app: fresh })
      setNextStage(fresh.allowed_next_stages[0]?.value ?? '')
    },
    [id],
  )

  const reload = useCallback(async () => {
    const current = ++requestId.current
    const fresh = await getApplication(id)
    if (current === requestId.current) show(fresh)
  }, [id, show])

  useEffect(() => {
    reload().catch((err: Error) => setLoaded({ id, error: err }))
  }, [id, reload])

  async function submitStage(event: FormEvent) {
    event.preventDefault()
    if (!app || !nextStage) return
    const label = app.allowed_next_stages.find((s) => s.value === nextStage)?.label
    if (
      TERMINAL.includes(nextStage) &&
      !window.confirm(`Move ${app.name} to ${label}? This can't be undone.`)
    ) {
      return
    }
    setStageBusy(true)
    setStageError(null)
    try {
      // The stage endpoint answers with the updated application.
      show(await changeStage(id, nextStage))
    } catch (err) {
      setStageError((err as Error).message)
    } finally {
      setStageBusy(false)
    }
  }

  async function submitNote(event: FormEvent) {
    event.preventDefault()
    if (!note.trim()) return
    setNoteBusy(true)
    setNoteError(null)
    try {
      await addNote(id, note.trim())
      setNote('')
      await reload()
    } catch (err) {
      // Keep the typed note so it isn't lost.
      setNoteError((err as Error).message)
    } finally {
      setNoteBusy(false)
    }
  }

  const backLink = (
    <Link to={`/${listSearch}`} className="back">
      ← Back to list
    </Link>
  )

  if (loadError) {
    return (
      <>
        {backLink}
        <ErrorBox error={loadError} />
      </>
    )
  }
  if (!app) {
    return (
      <>
        {backLink}
        <p className="muted">Loading…</p>
      </>
    )
  }

  const lastIndex = app.history.length - 1

  return (
    <>
      {backLink}

      <div className="page-head">
        <div>
          <h1>{app.name}</h1>
          <a href={`mailto:${app.email}`} className="muted">
            {app.email}
          </a>
        </div>
        <StageBadge stage={app.stage} />
      </div>

      <div className="detail-grid">
        <div className="stack">
          <section className="card">
            <h2>Application</h2>
            <dl className="facts">
              <dt>Submitted</dt>
              <dd>{formatDateTime(app.submitted_at)}</dd>
              <dt>Receipt</dt>
              <dd className="mono break">{app.receipt}</dd>
              <dt>Resume</dt>
              <dd>
                <ExternalLink href={app.resume_link} />
              </dd>
              <dt>Repository</dt>
              <dd>
                <ExternalLink href={app.repository_link} />
              </dd>
              <dt>Action run</dt>
              <dd>
                <ExternalLink href={app.action_run_link} />
              </dd>
            </dl>
          </section>

          <section className="card">
            <h2>History</h2>
            <ol className="timeline">
              {app.history.map((entry, index) => (
                <li
                  key={`${entry.stage.value}-${entry.entered_at}`}
                  className={index === lastIndex ? 'current' : undefined}
                >
                  <div className="timeline-head">
                    <StageBadge stage={entry.stage} />
                    <span className="muted small">{formatDateTime(entry.entered_at)}</span>
                    {index === lastIndex && <span className="current-tag">Current</span>}
                  </div>
                  {entry.notes.length === 0 ? (
                    <p className="muted small">No notes.</p>
                  ) : (
                    <ul className="notes">
                      {entry.notes.map((n) => (
                        <li key={n.id}>
                          <p>{n.content}</p>
                          <span className="muted small">{formatDateTime(n.created_at)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ol>
          </section>
        </div>

        <aside className="stack">
          <section className="card">
            <h2>Stage</h2>
            {app.allowed_next_stages.length === 0 ? (
              <p className="muted">Final stage. No further moves.</p>
            ) : (
              <form onSubmit={submitStage} className="stack-sm">
                <label>
                  Move to
                  <select
                    value={nextStage}
                    onChange={(e) => setNextStage(e.target.value as StageValue)}
                    disabled={stageBusy}
                  >
                    {app.allowed_next_stages.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="submit" className="btn btn-primary" disabled={stageBusy}>
                  {stageBusy ? 'Moving…' : 'Move'}
                </button>
                {stageError && <div className="alert">{stageError}</div>}
              </form>
            )}
          </section>

          <section className="card">
            <h2>Add note</h2>
            <form onSubmit={submitNote} className="stack-sm">
              <p className="muted small">
                Note will be added to: <strong>{app.stage.label}</strong>
              </p>
              <textarea
                rows={4}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="What happened at this stage?"
                disabled={noteBusy}
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={noteBusy || !note.trim()}
              >
                {noteBusy ? 'Saving…' : 'Save note'}
              </button>
              {noteError && <div className="alert">{noteError}</div>}
            </form>
          </section>
        </aside>
      </div>
    </>
  )
}

function ExternalLink({ href }: { href: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="break">
      {href}
    </a>
  )
}
