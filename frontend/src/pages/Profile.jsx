import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api'
import { useAuth } from '../auth'
import { ErrorNote, Loading, useAsync } from '../components/ui'

export default function Profile() {
  const { setUser } = useAuth()
  const { data, error, loading, reload } = useAsync(() => api.get('/api/profile'), [])
  const [name, setName] = useState(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  if (loading && !data) return <Loading />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  const value = name ?? data.name
  async function save(e) {
    e.preventDefault()
    setErr(''); setMsg('')
    try {
      const u = await api.patch('/api/profile', { name: value })
      setUser({ id: u.id, name: u.name, email: u.email, role: u.role })
      setMsg('Profile updated.'); setName(null); reload(true)
    } catch (x) { setErr(x.message) }
  }
  return (
    <>
      <div className="page-head"><div className="stack" style={{ gap: 8 }}><span className="eyebrow">Account</span><h1>Profile</h1></div><Link className="btn" to="/settings">Settings</Link></div>
      <div className="grid g2" style={{ alignItems: 'start' }}>
        <form className="card stack" onSubmit={save}>
          <label className="field"><span>Name</span><input type="text" required minLength={2} maxLength={80} value={value} onChange={(e) => setName(e.target.value)} /></label>
          <label className="field"><span>Email</span><input type="email" value={data.email} readOnly disabled /></label>
          <label className="field"><span>Role</span><input type="text" value={data.role} readOnly disabled /></label>
          {msg && <div className="note ok">{msg}</div>}<ErrorNote error={err} />
          <div><button className="btn primary" disabled={value === data.name}>Save changes</button></div>
        </form>
        <div className="grid g2">
          <div className="stat"><span>Searches</span><b>{data.search_count}</b></div>
          <div className="stat"><span>Account created</span><b style={{ fontSize: '1.2rem' }}>{api.fmtDay(data.created_at)}</b></div>
          <div className="stat"><span>Last sign-in</span><b style={{ fontSize: '1.2rem' }}>{api.fmtDate(data.last_login_at)}</b></div>
          <div className="stat"><span>Status</span><b style={{ fontSize: '1.2rem' }}>{data.is_active ? 'Active' : 'Inactive'}</b></div>
        </div>
      </div>
    </>
  )
}
