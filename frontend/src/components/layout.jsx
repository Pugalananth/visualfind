import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth, homeFor } from '../auth'
import { Brand } from './ui'

export function PublicNav() {
  const { authenticated, user } = useAuth()
  return (
    <header className="pubnav">
      <div className="wrap">
        <Brand />
        <nav aria-label="Primary">
          <a href="/#how">How it Works</a>
          <a href="/#features">Features</a>
          <Link to="/search/new">Search</Link>
          <a href="/#about">About</a>
        </nav>
        <div className="row">
          {authenticated ? <Link className="btn primary small" to={homeFor(user)}>Open workspace</Link> : (
            <>
              <Link className="btn small" to="/login">Login</Link>
              <Link className="btn primary small" to="/register">Sign Up</Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="wrap">
        <span>© {new Date().getFullYear()} VisualFind</span>
        <span><Link to="/privacy">Privacy &amp; data handling</Link><Link to="/terms">Terms</Link></span>
      </div>
    </footer>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const nav = useNavigate()
  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const initials = user.name.split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase()
  return (
    <div className="menu" ref={ref}>
      <button onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>
        <span className="avatar">{initials}</span><span className="uname">{user.name}</span>
      </button>
      {open && (
        <div className="dropdown" role="menu" onClick={() => setOpen(false)}>
          <div className="who"><b>{user.name}</b><span className="muted" style={{ fontSize: '.8rem' }}>{user.email} · {user.role}</span></div>
          <Link to="/profile">Profile</Link>
          <Link to="/settings">Settings</Link>
          {user.role === 'ADMIN' && <Link to="/admin">Admin console</Link>}
          <button onClick={async () => { await logout(); nav('/login') }}>Sign out</button>
        </div>
      )}
    </div>
  )
}

export function AppShell() {
  const { user } = useAuth()
  return (
    <>
      <header className="topbar">
        <div className="wrap">
          <Brand to={homeFor(user)} />
          <nav aria-label="Workspace">
            <NavLink to="/dashboard">Dashboard</NavLink>
            <NavLink to="/search/new">Search</NavLink>
            <NavLink to="/history">History</NavLink>
            <NavLink to="/profile">Profile</NavLink>
          </nav>
          <UserMenu />
        </div>
      </header>
      <main className="wrap page"><Outlet /></main>
    </>
  )
}

const ADMIN_LINKS = [
  ['/admin', 'Overview', true], ['/admin/users', 'Users'], ['/admin/searches', 'Searches'], ['/admin/jobs', 'Jobs'],
  ['/admin/system', 'System'], ['/admin/audit-logs', 'Audit Logs'], ['/admin/settings', 'Settings'],
]

export function AdminShell() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  return (
    <div className="admin-shell">
      <aside className="sidebar">
        <div><Brand to="/admin" /><div className="eyebrow" style={{ marginTop: 8 }}>Administration</div></div>
        <nav aria-label="Admin">
          {ADMIN_LINKS.map(([to, label, end]) => <NavLink key={to} to={to} end={end}>{label}</NavLink>)}
        </nav>
        <div className="bottom">
          <Link className="btn small" to="/dashboard">User workspace</Link>
          <span className="muted" style={{ fontSize: '.78rem' }}>{user.email}</span>
          <button className="btn small" onClick={async () => { await logout(); nav('/login') }}>Sign out</button>
        </div>
      </aside>
      <main className="admin-main"><Outlet /></main>
    </div>
  )
}
