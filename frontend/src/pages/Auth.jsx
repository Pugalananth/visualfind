import { useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import { homeFor, useAuth } from '../auth'
import { Brand, ErrorNote, useAsync } from '../components/ui'

function Shell({ title, sub, children }) {
  return (
    <div className="auth">
      <div className="side">
        <Brand />
        <blockquote>“Show it one image. It shows you every moment that image appears.”</blockquote>
        <span className="hint">VisualFind · visual search for video</span>
      </div>
      <div className="form">
        <div className="stack" style={{ width: 'min(400px,100%)' }}>
          <div className="stack" style={{ gap: 8 }}><h2>{title}</h2>{sub && <p className="muted">{sub}</p>}</div>
          {children}
        </div>
      </div>
    </div>
  )
}

export function Login() {
  const { login } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [email, setEmail] = useState(loc.state?.email || '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const notice = loc.state?.registered ? 'Account created. Sign in to continue.' : loc.state?.reset ? 'Password updated. Sign in with your new password.' : ''

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const user = await login(email, password)
      const from = loc.state?.from
      const adminOk = user.role === 'ADMIN' || !from?.startsWith('/admin')
      nav(from && adminOk ? from : homeFor(user), { replace: true })
    } catch (err) {
      setError(err.kind === 'auth' ? 'Invalid email or password.' : err.message)
      setBusy(false)
    }
  }
  return (
    <Shell title="Sign in" sub="Welcome back to VisualFind.">
      {notice && <div className="note ok">{notice}</div>}
      <form onSubmit={submit}>
        <label className="field"><span>Email</span><input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="field"><span>Password</span><input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        <ErrorNote error={error} />
        <button className="btn primary big" disabled={busy}>{busy ? 'Signing in…' : 'Login'}</button>
      </form>
      <div className="row between"><Link to="/forgot-password">Forgot password?</Link><span className="muted">No account? <Link to="/register">Register</Link></span></div>
    </Shell>
  )
}

export function PasswordRules({ password, min }) {
  const rules = useMemo(() => [
    [`At least ${min} characters`, password.length >= min], ['A lowercase letter', /[a-z]/.test(password)],
    ['An uppercase letter', /[A-Z]/.test(password)], ['A digit', /\d/.test(password)],
  ], [password, min])
  return <div className="rules" aria-live="polite">{rules.map(([t, ok]) => <span key={t} className={ok ? 'met' : ''}>{ok ? '✓' : '○'} {t}</span>)}</div>
}

export function Register() {
  const nav = useNavigate()
  const { data: policy } = useAsync(() => api.get('/api/public/policy', { auth: false }), [])
  const min = policy?.min_password_length || 8
  const [f, setF] = useState({ name: '', email: '', password: '', confirm_password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const mismatch = f.confirm_password && f.password !== f.confirm_password

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (f.password !== f.confirm_password) return setError('Passwords do not match.')
    setBusy(true)
    try {
      await api.post('/api/auth/register', f, { auth: false })
      nav('/login', { replace: true, state: { registered: true, email: f.email } })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return (
    <Shell title="Create your account" sub="Start searching your video visually.">
      {policy && !policy.registration_enabled && <div className="note error">Registration is currently disabled by the administrator.</div>}
      <form onSubmit={submit}>
        <label className="field"><span>Full name</span><input type="text" autoComplete="name" required minLength={2} value={f.name} onChange={set('name')} /></label>
        <label className="field"><span>Email</span><input type="email" autoComplete="email" required value={f.email} onChange={set('email')} /></label>
        <label className="field"><span>Password</span><input type="password" autoComplete="new-password" required value={f.password} onChange={set('password')} /></label>
        <PasswordRules password={f.password} min={min} />
        <label className="field"><span>Confirm password</span><input type="password" autoComplete="new-password" required value={f.confirm_password} onChange={set('confirm_password')} />{mismatch && <span className="err" style={{ textTransform: 'none', letterSpacing: 0 }}>Passwords do not match.</span>}</label>
        <ErrorNote error={error} />
        <button className="btn primary big" disabled={busy}>{busy ? 'Creating account…' : 'Register'}</button>
      </form>
      <span className="muted">Already registered? <Link to="/login">Sign in</Link></span>
    </Shell>
  )
}

export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [done, setDone] = useState(null)
  const [error, setError] = useState('')
  async function submit(e) {
    e.preventDefault()
    setError('')
    try { setDone(await api.post('/api/auth/forgot-password', { email }, { auth: false })) } catch (err) { setError(err.message) }
  }
  return (
    <Shell title="Reset your password" sub="Enter your account email and we will issue a reset link.">
      {done ? (
        <div className="stack">
          <div className="note ok">If an account exists for that address, a reset link has been issued. It expires in one hour.</div>
          {!done.email_delivery && <div className="note">Email delivery is not configured on this server, so the link was not emailed. An administrator can retrieve it from the server log.</div>}
        </div>
      ) : (
        <form onSubmit={submit}>
          <label className="field"><span>Email</span><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <ErrorNote error={error} />
          <button className="btn primary big">Send reset link</button>
        </form>
      )}
      <Link to="/login">Back to sign in</Link>
    </Shell>
  )
}

export function ResetPassword() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const token = params.get('token') || ''
  const [f, setF] = useState({ password: '', confirm_password: '' })
  const [error, setError] = useState('')
  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/api/auth/reset-password', { token, ...f }, { auth: false })
      nav('/login', { replace: true, state: { reset: true } })
    } catch (err) { setError(err.message) }
  }
  if (!token) return <Shell title="Invalid link"><div className="note error">This reset link is missing its token.</div><Link to="/forgot-password">Request a new link</Link></Shell>
  return (
    <Shell title="Choose a new password">
      <form onSubmit={submit}>
        <label className="field"><span>New password</span><input type="password" autoComplete="new-password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
        <PasswordRules password={f.password} min={8} />
        <label className="field"><span>Confirm password</span><input type="password" autoComplete="new-password" required value={f.confirm_password} onChange={(e) => setF({ ...f, confirm_password: e.target.value })} /></label>
        <ErrorNote error={error} />
        <button className="btn primary big">Update password</button>
      </form>
    </Shell>
  )
}
