import { useState } from 'react'
import { Link } from 'react-router-dom'
import { postSubmission, type SubmissionResult } from '../api'
import { canonicalJson, shellSnippet, sign, type SubmissionPayload } from '../signing'

// Each button sends one kind of request. The label is what the log shows.
type Scenario = {
  key: 'signed' | 'wrong_secret' | 'unsigned' | 'missing_field' | 'bad_json'
  label: string
  expect: string
}

const SCENARIOS: Scenario[] = [
  { key: 'signed', label: 'Send signed', expect: '200 and a receipt' },
  { key: 'wrong_secret', label: 'Wrong secret', expect: '401 signature_mismatch' },
  { key: 'unsigned', label: 'No signature', expect: '401 missing_signature' },
  { key: 'missing_field', label: 'Signed, no email', expect: '400 validation_failed' },
  { key: 'bad_json', label: 'Signed, not JSON', expect: '400 invalid_json' },
]

type Attempt = { id: number; label: string; expect: string; result: SubmissionResult }

const FIELDS: { name: keyof typeof DEFAULTS; label: string }[] = [
  { name: 'name', label: 'Name' },
  { name: 'email', label: 'Email' },
  { name: 'resume_link', label: 'Resume link' },
  { name: 'repository_link', label: 'Repository link' },
  { name: 'action_run_link', label: 'Action run link' },
]

const DEFAULTS = {
  name: 'Test Applicant',
  email: 'test.applicant@example.com',
  resume_link: 'https://example.com/resume.pdf',
  repository_link: 'https://github.com/example/application-submitter',
  action_run_link: 'https://github.com/example/application-submitter/actions/runs/1',
}

function receiptOf(result: SubmissionResult): string | null {
  const body = result.body
  if (body && typeof body === 'object' && 'receipt' in body) {
    return String((body as { receipt: unknown }).receipt)
  }
  return null
}

export default function SubmissionTestPage() {
  const [secret, setSecret] = useState('')
  const [fields, setFields] = useState(DEFAULTS)
  const [busy, setBusy] = useState<Scenario['key'] | null>(null)
  const [attempts, setAttempts] = useState<Attempt[]>([])
  const [problem, setProblem] = useState<string | null>(null)

  const payload: SubmissionPayload = { ...fields, timestamp: new Date().toISOString() }
  const preview = canonicalJson(payload)

  async function run(scenario: Scenario) {
    setBusy(scenario.key)
    setProblem(null)
    try {
      const body: SubmissionPayload = { ...fields, timestamp: new Date().toISOString() }
      if (scenario.key === 'missing_field') delete body.email
      const canonical = canonicalJson(body)
      let raw = canonical
      let signature: string | null = null
      if (scenario.key !== 'unsigned') {
        signature = await sign(canonical, scenario.key === 'wrong_secret' ? `${secret}x` : secret)
      }
      if (scenario.key === 'bad_json') raw = canonical.slice(0, -1)
      const result = await postSubmission(raw, signature)
      setAttempts((log) => [
        { id: log.length + 1, label: scenario.label, expect: scenario.expect, result },
        ...log,
      ])
    } catch (err) {
      setProblem(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Try the submission endpoint</h1>
        <p className="muted">
          This is what the applicant's GitHub Action does: sign the JSON with HMAC-SHA256 and
          POST it to <code>/submission</code>. A good signature gets a receipt and a row in{' '}
          <Link to="/">the list</Link>. Anything else gets the gist's error code.
        </p>
      </div>

      <div className="detail-grid">
        <div className="stack">
          <section className="card">
            <h2>Payload</h2>
            <div className="stack-sm">
              <label>
                Signing secret
                <input
                  type="password"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  placeholder="APPLICANT_SIGNING_SECRET of this deployment"
                  autoComplete="off"
                />
              </label>
              {FIELDS.map((f) => (
                <label key={f.name}>
                  {f.label}
                  <input
                    value={fields[f.name]}
                    onChange={(e) => setFields({ ...fields, [f.name]: e.target.value })}
                  />
                </label>
              ))}
              <p className="muted small">
                <code>timestamp</code> is set to now on each send. The bytes that get signed:
              </p>
              <pre className="code break">{preview}</pre>
            </div>
          </section>

          <section className="card">
            <h2>Send</h2>
            <div className="button-row">
              {SCENARIOS.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  className={`btn ${s.key === 'signed' ? 'btn-primary' : 'btn-ghost'}`}
                  disabled={busy !== null || !secret}
                  onClick={() => run(s)}
                  title={`Expect ${s.expect}`}
                >
                  {busy === s.key ? 'Sending…' : s.label}
                </button>
              ))}
            </div>
            {!secret && <p className="muted small">Enter the signing secret to enable sending.</p>}
            {problem && <div className="alert">{problem}</div>}
          </section>

          <section className="card">
            <h2>Same request from a shell</h2>
            <pre className="code break">{shellSnippet(window.location.origin, preview)}</pre>
          </section>
        </div>

        <aside className="stack">
          <section className="card">
            <h2>Responses</h2>
            {attempts.length === 0 ? (
              <p className="muted">Nothing sent yet.</p>
            ) : (
              <ol className="attempts">
                {attempts.map((a) => {
                  const receipt = receiptOf(a.result)
                  const ok = a.result.status === 200
                  return (
                    <li key={a.id} className={ok ? 'attempt ok' : 'attempt'}>
                      <div className="attempt-head">
                        <span className="strong">{a.label}</span>
                        <span className={`status ${ok ? 'status-ok' : 'status-bad'}`}>
                          {a.result.status}
                        </span>
                      </div>
                      <span className="muted small">Expected {a.expect}</span>
                      <pre className="code break">{JSON.stringify(a.result.body, null, 2)}</pre>
                      {receipt && (
                        <Link to={`/?receipt=${encodeURIComponent(receipt)}`} className="small">
                          Open this application in the list
                        </Link>
                      )}
                    </li>
                  )
                })}
              </ol>
            )}
          </section>
        </aside>
      </div>
    </>
  )
}
