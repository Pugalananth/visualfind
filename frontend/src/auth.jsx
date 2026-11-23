import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import * as api from './api'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: 'loading', user: null, error: null })

  const clear = useCallback(() => {
    api.setToken(null)
    setState({ status: 'anon', user: null, error: null })
  }, [])

  const restore = useCallback(async () => {
    if (!api.getToken()) return setState({ status: 'anon', user: null, error: null })
    setState((s) => ({ ...s, status: 'loading', error: null }))
    try {
      const user = await api.get('/api/auth/me')
      setState({ status: 'authed', user, error: null })
    } catch (e) {
      if (e.kind === 'auth' || e.kind === 'forbidden') clear()
      else setState({ status: 'error', user: null, error: e.message })
    }
  }, [clear])

  useEffect(() => {
    api.setUnauthorizedHandler(clear)
    restore()
  }, [clear, restore])

  const login = useCallback(async (email, password) => {
    const res = await api.post('/api/auth/login', { email, password }, { auth: false })
    api.setToken(res.access_token)
    setState({ status: 'authed', user: res.user, error: null })
    return res.user
  }, [])

  const logout = useCallback(async () => {
    try { await api.post('/api/auth/logout') } catch { /* token may already be invalid */ }
    clear()
  }, [clear])

  const value = useMemo(() => ({
    ...state, authenticated: state.status === 'authed', role: state.user?.role,
    login, logout, restore, setUser: (user) => setState((s) => ({ ...s, user })),
  }), [state, login, logout, restore])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function Splash({ error, onRetry }) {
  return (
    <div className="splash">
      <div className="brand-mark" />
      {error ? (
        <>
          <p className="muted">{error}</p>
          <button className="btn" onClick={onRetry}>Retry</button>
        </>
      ) : <div className="spinner" aria-label="Loading" />}
    </div>
  )
}

export function homeFor(user) { return user?.role === 'ADMIN' ? '/admin' : '/dashboard' }

export function RequireAuth({ role, children }) {
  const { status, user, error, restore } = useAuth()
  const loc = useLocation()
  if (status === 'loading') return <Splash />
  if (status === 'error') return <Splash error={error} onRetry={restore} />
  if (status === 'anon') return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />
  if (role === 'ADMIN' && user.role !== 'ADMIN') return <Navigate to="/dashboard" replace />
  return children
}

export function PublicOnly({ children }) {
  const { status, user } = useAuth()
  if (status === 'loading') return <Splash />
  if (status === 'authed') return <Navigate to={homeFor(user)} replace />
  return children
}
