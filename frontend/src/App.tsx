import { Link, Outlet } from 'react-router-dom'
import { DEMO, resetDemo } from './api'

export default function App() {
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            <span className="brand-mark">B12</span>
            <span className="brand-name">Applicants</span>
          </Link>
          {!DEMO && (
            <a className="topbar-link" href="/admin/">
              Admin
            </a>
          )}
        </div>
      </header>
      {DEMO && (
        <div className="demo-banner">
          <div className="demo-banner-inner">
            <span>
              <strong>Demo.</strong> Sample data lives in your browser, so notes and stage changes
              stay on this device. The real app talks to the Django API in this repo.
            </span>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                resetDemo()
                window.location.reload()
              }}
            >
              Reset data
            </button>
          </div>
        </div>
      )}
      <main className="container">
        <Outlet />
      </main>
    </>
  )
}
