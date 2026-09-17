import { Link, Outlet } from 'react-router-dom'

export default function App() {
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            <span className="brand-mark">B12</span>
            <span className="brand-name">Applicants</span>
          </Link>
          <nav className="topbar-links">
            <Link className="topbar-link" to="/submit">
              Test submission
            </Link>
            <a className="topbar-link" href="/admin/">
              Admin
            </a>
          </nav>
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  )
}
