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
          <a className="topbar-link" href="/admin/">
            Admin
          </a>
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  )
}
