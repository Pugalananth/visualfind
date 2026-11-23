import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import * as api from '../api'
import { useAuth } from '../auth'
import { PasswordRules } from './Auth'
import { Confirm, ErrorNote, Loading, useAsync } from '../components/ui'

function ProfileTab({ profile, reload }) {
  const { setUser } = useAuth()
  const [name, setName] = useState(profile.name)
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  async function save(e) {
    e.preventDefault(); setMsg(''); setErr('')
    try { const u = await api.patch('/api/profile', { name }); setUser({ id: u.id, name: u.name, email: u.email, role: u.role }); setMsg('Profile updated.'); reload(true) } catch (x) { setErr(x.message) }
  }
  return (
    <form className="card stack" style={{ maxWidth: 520 }} onSubmit={save}>
      <label className="field"><span>Name</span><input type="text" required minLength={2} value={name} onChange={(e) => setName(e.target.value)} /></label>
      <label className="field"><span>Email</span><input type="email" value={profile.email} disabled /></label>
      <span className="hint">Role and account status can only be changed by an administrator.</span>
      {msg && <div className="note ok">{msg}</div>}<ErrorNote error={err} />
      <div><button className="btn primary">Save</button></div>
    </form>
  )
}

function PasswordTab() {
  const { restore } = useAuth()
  const [f, setF] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  const { data: policy } = useAsync(() => api.get('/api/public/policy', { auth: false }), [])
  async function save(e) {
    e.preventDefault(); setMsg(''); setErr('')
    try {
      const r = await api.post('/api/profile/password', f)
      api.setToken(r.access_token)  // other sessions are signed out; keep this one
      setF({ current_password: '', new_password: '', confirm_password: '' }); setMsg('Password changed. Other sessions were signed out.'); restore()
    } catch (x) { setErr(x.message) }
  }
  return (
    <form className="card stack" style={{ maxWidth: 520 }} onSubmit={save}>
      <label className="field"><span>Current password</span><input type="password" autoComplete="current-password" required value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} /></label>
      <label className="field"><span>New password</span><input type="password" autoComplete="new-password" required value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} /></label>
      <PasswordRules password={f.new_password} min={policy?.min_password_length || 8} />
      <label className="field"><span>Confirm new password</span><input type="password" autoComplete="new-password" required value={f.confirm_password} onChange={(e) => setF({ ...f, confirm_password: e.target.value })} /></label>
      {msg && <div className="note ok">{msg}</div>}<ErrorNote error={err} />
      <div><button className="btn primary">Change password</button></div>
    </form>
  )
}

function PrivacyTab() {
  const { data: policy } = useAsync(() => api.get('/api/public/policy', { auth: false }), [])
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  async function clear() {
    setMsg(''); setErr('')
    try { const r = await api.del('/api/history'); setMsg(`Deleted ${r.deleted} search${r.deleted === 1 ? '' : 'es'} and their stored media.`) } catch (x) { setErr(x.message) }
  }
  return (
    <div className="card stack" style={{ maxWidth: 640 }}>
      <p className="muted">Your reference images, uploaded videos and match frames are kept {policy ? (policy.retention_days === 0 ? 'until you delete them' : `for ${policy.retention_days} day(s)`) : '…'}. Only you and administrators can see your history. Read the full <Link to="/privacy">privacy and data handling</Link> page.</p>
      <div className="row between"><div><b>Delete my search history</b><br /><span className="hint">Removes all finished searches, results and stored media. Cannot be undone.</span></div><Confirm text="Delete everything?" onConfirm={clear} className="btn danger">Delete history</Confirm></div>
      {msg && <div className="note ok">{msg}</div>}<ErrorNote error={err} />
    </div>
  )
}

function NotificationsTab({ profile, reload }) {
  const [on, setOn] = useState(profile.notify_on_complete)
  const [err, setErr] = useState('')
  async function toggle(v) {
    setOn(v); setErr('')
    try { await api.patch('/api/profile', { notify_on_complete: v }); reload(true) } catch (x) { setOn(!v); setErr(x.message) }
  }
  return (
    <div className="card stack" style={{ maxWidth: 560 }}>
      <label className="check"><input type="checkbox" checked={on} onChange={(e) => toggle(e.target.checked)} /><span><b>Email me when a search finishes</b><br /><span className="hint">Sent to {profile.email}.</span></span></label>
      {!profile.email_delivery && <div className="note">Email delivery is not configured on this server yet, so this preference will take effect once an administrator sets up SMTP.</div>}
      <ErrorNote error={err} />
    </div>
  )
}

export default function Settings() {
  const [tab, setTab] = useState('profile')
  const { data, error, loading, reload } = useAsync(() => api.get('/api/profile'), [])
  return (
    <>
      <div className="page-head"><div className="stack" style={{ gap: 8 }}><span className="eyebrow">Account</span><h1>Settings</h1></div></div>
      <div className="tabs" role="tablist">{[['profile', 'Profile'], ['password', 'Password'], ['privacy', 'Privacy'], ['notifications', 'Notifications']].map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
      {loading && !data ? <Loading /> : error ? <ErrorNote error={error} onRetry={reload} /> : (
        <>
          {tab === 'profile' && <ProfileTab profile={data} reload={reload} />}
          {tab === 'password' && <PasswordTab />}
          {tab === 'privacy' && <PrivacyTab />}
          {tab === 'notifications' && <NotificationsTab profile={data} reload={reload} />}
        </>)}
    </>
  )
}
