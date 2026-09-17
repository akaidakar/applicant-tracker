import { ApiError, LOGIN_URL } from './api'
import type { Stage } from './types'

export function StageBadge({ stage }: { stage: Stage }) {
  return <span className={`badge badge-${stage.value}`}>{stage.label}</span>
}

export function ErrorBox({ error }: { error: Error }) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return (
      <div className="alert">
        You need to sign in. <a href={LOGIN_URL}>Log in with your staff account</a>, then come
        back.
      </div>
    )
  }
  return <div className="alert">{error.message}</div>
}
